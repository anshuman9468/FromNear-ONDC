import asyncio
from uuid import uuid4

from app.ondc.bpp import lifecycle
from app.ondc.bpp.client import bpp_client


def test_rto_statuses_match_pramaan_fulfillment_selectors_on_wire(monkeypatch):
    """Pramaan finds statuses by fulfillment type and state, not UI step ID."""
    wire_calls = []
    ctx = {
        "transaction_id": str(uuid4()), "message_id": str(uuid4()),
        "domain": "ONDC:RET10", "core_version": "1.2.0",
        "country": "IND", "city": "std:080",
        "bap_id": "workbench.ondc.tech",
        "bap_uri": "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/buyer",
        "bpp_id": "ondc.fromnear.com",
    }
    order = {"id": "rto-wire-test", "items": [{"id": "I1", "quantity": {"count": 1}}],
             "fulfillments": [{"id": "F1", "type": "Delivery"}]}
    payload = {"context": ctx, "message": {"order": order}}

    async def no_delay(_seconds):
        return None

    async def capture(context, action, message):
        wire_calls.append((action, bpp_client._canonicalize_message(context, action, message)))

    monkeypatch.setattr(lifecycle.asyncio, "sleep", no_delay)
    monkeypatch.setattr(lifecycle, "is_rto_flow", lambda *a, **k: True)
    monkeypatch.setattr(lifecycle, "is_buyer_cancel_flow", lambda *a: False)
    monkeypatch.setattr(lifecycle.lifecycle_tracker, "is_cancelled", lambda _tx: False)
    monkeypatch.setattr(lifecycle.lifecycle_tracker, "get_callback_context", lambda _tx, c: c)
    monkeypatch.setattr(lifecycle.lifecycle_tracker, "record_callback", lambda *a: None)
    monkeypatch.setattr(bpp_client, "send_unsolicited", capture)

    async def run():
        await lifecycle.push_post_confirm_lifecycle(ctx, payload, order["id"], "2026-10-27T00:00:00.000Z", order)
        await lifecycle.push_rto_final_status(ctx, payload, order["id"], "2026-10-27T00:00:00.000Z", order)

    asyncio.run(run())
    statuses = [message["order"] for action, message in wire_calls if action == "on_status"]
    assert len(statuses) == 2
    assert statuses[0]["state"] == "Accepted"
    assert any(f["type"] == "Delivery" and f["state"]["descriptor"]["code"] == "Pending"
               for f in statuses[0]["fulfillments"])
    assert statuses[1]["state"] == "Cancelled"
    assert any(f["type"] == "RTO" and f["state"]["descriptor"]["code"] == "RTO-Delivered"
               for f in statuses[1]["fulfillments"])
    assert [action for action, _ in wire_calls] == ["on_status", "on_update", "on_status"]


def test_second_rto_update_emits_rto_delivered_on_status(monkeypatch):
    calls = []
    recorded = []

    async def no_delay(_seconds):
        return None

    async def capture_callback(context, action, order, unsolicited):
        calls.append((context, action, order, unsolicited))

    def capture_build(**kwargs):
        calls.append(kwargs)
        return {"id": kwargs["order_id"], "state": kwargs["order_state"]}

    monkeypatch.setattr(lifecycle.asyncio, "sleep", no_delay)
    monkeypatch.setattr(lifecycle.lifecycle_tracker, "is_cancelled", lambda _tx: False)
    monkeypatch.setattr(lifecycle, "build_canonical_order", capture_build)
    monkeypatch.setattr(lifecycle, "_send_lifecycle_callback", capture_callback)
    monkeypatch.setattr(
        lifecycle.lifecycle_tracker,
        "record_callback",
        lambda *args: recorded.append(args),
    )

    asyncio.run(
        lifecycle.push_rto_final_status(
            context={
                "transaction_id": "rto-final-update-test",
                "bpp_id": "ondc.fromnear.com",
            },
            payload={"context": {}, "message": {"order": {}}},
            order_id="ORDER-RTO-1",
            created_at="2026-10-21T00:00:00.000Z",
            stored_order={"items": [], "fulfillments": []},
        )
    )

    build_call, callback_call = calls
    assert build_call["action"] == "on_status"
    assert build_call["state_code"] == lifecycle.RET10_FULFILLMENT_STATE["RTO_DELIVERED"]
    assert build_call["order_state"] == "Cancelled"
    assert callback_call[1] == "on_status"
    assert callback_call[2]["cancellation"]["reason"]["id"] == "011"
    assert callback_call[3] is True
    assert recorded == [
        (
            "rto-final-update-test",
            "on_status",
            lifecycle.RET10_FULFILLMENT_STATE["RTO_DELIVERED"],
        )
    ]
