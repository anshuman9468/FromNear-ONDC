"""Regressions from the 2026-10-26 Workbench report; no live requests."""
import asyncio
import json
import uuid
from unittest.mock import AsyncMock

from app.ondc.bpp import lifecycle, order_builder
from app.ondc.bpp.services.select import BppSelectService
from app.ondc.bpp.services.update import BppUpdateService
from app.ondc.bpp.client import bpp_client


def context():
    return {
        "transaction_id": str(uuid.uuid4()), "message_id": str(uuid.uuid4()),
        "bap_id": "workbench.ondc.tech", "domain": "ONDC:RET10",
        "core_version": "1.2.0", "city": "std:080", "country": "IND",
        "bap_uri": "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/buyer",
    }


def test_prepaid_terms_are_not_a_merchant_cancellation(monkeypatch):
    monkeypatch.setattr(lifecycle.settings, "ONDC_BPP_FLOW_MODE", "auto")
    payload = {"context": context(), "message": {"order": {"tags": [{
        "code": "bpp_terms", "list": [
            {"code": key, "value": "value"}
            for key in ("np_type", "tax_number", "provider_tax_number")
        ],
    }]}}}
    assert not lifecycle.is_rto_flow(payload["context"], payload)


def test_shortage_then_corrected_selection_and_repeat_succeed(monkeypatch):
    monkeypatch.setattr(lifecycle.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(order_builder, "_get_catalog_item_map", lambda: {
        "I1": {"location_id": "L1", "parent_item_id": "V1", "fulfillment_id": "F1", "quantity": {"available": {"count": "2"}},
               "price": {"value": "250", "currency": "INR"}},
    })
    success, failure = AsyncMock(), AsyncMock()
    monkeypatch.setattr(bpp_client, "send_callback", success)
    monkeypatch.setattr(bpp_client, "send_callback_error", failure)
    ctx = context()

    async def run():
        for count in (3, 1, 1):
            await BppSelectService().process_select({
                "context": {**ctx, "message_id": str(uuid.uuid4())},
                "message": {"order": {"items": [{"id": "I1", "quantity": {"count": count}}]}},
            })
    asyncio.run(run())
    assert success.await_count == 2
    assert failure.await_count == 1
    error = failure.call_args.args[2]
    assert error["code"] == "40002"
    assert json.loads(error["message"]) == [{"item_id": "I1", "error": "40002"}]
    assert failure.call_args.args[3]["order"]["items"][0]["quantity"]["count"] == 0


def test_return_callbacks_use_official_wire_state_names(monkeypatch):
    monkeypatch.setattr(lifecycle.asyncio, "sleep", AsyncMock())
    states = []

    async def capture(ctx, action, message):
        # Include the final network canonicalization in the regression.
        wire = bpp_client._canonicalize_message(ctx, action, message)
        states.append(wire["order"]["fulfillments"][0]["state"]["descriptor"]["code"])

    monkeypatch.setattr(bpp_client, "send_callback", capture)
    monkeypatch.setattr(bpp_client, "send_unsolicited", capture)
    ctx = context()

    async def run():
        for _ in range(2):
            await BppUpdateService().process_update({
                "context": {**ctx, "message_id": str(uuid.uuid4())},
                "message": {"order": {"id": "return-test", "items": [{"id": "I1", "quantity": {"count": 1}}],
                                      "fulfillments": [{"id": "R1", "type": "Return"}]}},
            })
    asyncio.run(run())
    assert states == ["Return_Initiated", "Return_Approved", "Return_Picked", "Return_Delivered"]


def test_error_selection_zero_survives_wire_canonicalization():
    wire = bpp_client._canonicalize_message(context(), "on_select", {"order": {
        "items": [{"id": "I1", "quantity": {"count": 0}}],
    }})
    assert wire["order"]["items"][0]["quantity"]["selected"]["count"] == 0


def test_opaque_prepaid_waits_for_track_before_final_delivery(monkeypatch):
    monkeypatch.setattr(lifecycle.settings, "ONDC_BPP_FLOW_MODE", "auto")
    monkeypatch.setattr(lifecycle.asyncio, "sleep", AsyncMock())
    callbacks = []

    async def capture(ctx, action, order, unsolicited):
        callbacks.append((action, order["fulfillments"][0]["state"]["descriptor"]["code"]))

    monkeypatch.setattr(lifecycle, "_send_lifecycle_callback", capture)
    ctx = context()
    payload = {"context": ctx, "message": {"order": {
        "items": [{"id": "I1", "quantity": {"count": 1}}],
        "tags": [{"code": "bpp_terms", "list": [
            {"code": k, "value": "test"} for k in ("np_type", "tax_number", "provider_tax_number")
        ]}],
    }}}
    asyncio.run(lifecycle.push_post_confirm_lifecycle(ctx, payload, "prepaid-test", "2026-10-26T00:00:00.000Z", {}))
    assert callbacks == [("on_status", state) for state in (
        "Pending", "Packed", "Agent-assigned", "Order-picked-up",
    )]
