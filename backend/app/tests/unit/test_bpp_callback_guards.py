import asyncio
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.ondc.bpp.client import BppNetworkClient
from app.ondc.bpp.order_builder import build_canonical_order, build_canonical_quote, validate_ret10_payload
from app.ondc.bpp.services.search import BppSearchService, _is_incremental_push, _normalize_catalog_quantities
from app.ondc.bpp.lifecycle import is_rto_flow
from app.ondc.bpp.state_machine import LifecycleTracker, lifecycle_tracker


CONTEXT = {
    "domain": "ONDC:RET10",
    "country": "IND",
    "city": "std:080",
    "core_version": "1.2.0",
    "bap_id": "workbench.ondc.tech",
    "bap_uri": "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/buyer",
    "bpp_id": "ondc.fromnear.com",
    "bpp_uri": "https://ondc.fromnear.com/api/v1/ondc",
    "transaction_id": "3c816eb3-9d23-4776-8acc-85c063277bf1",
    "message_id": "b82a9a80-469c-49a8-ae58-a395e7a1d83b",
    "timestamp": "2026-08-26T12:00:00.000Z",
}


def test_callback_guard_completes_sparse_lifecycle_order():
    message = BppNetworkClient._canonicalize_message(
        CONTEXT,
        "on_status",
        {
            "order": {
                "id": "ORDER-1",
                "state": "In-progress",
                "items": [{"id": "I1", "fulfillment_id": "F1"}],
                "fulfillments": [{"id": "F1", "state": {"descriptor": {"code": "Packed"}}}],
            }
        },
    )
    payload = {"context": {**CONTEXT, "action": "on_status"}, "message": message}

    assert validate_ret10_payload("on_status", payload) == []
    order = message["order"]
    assert order["items"][0]["parent_item_id"] == "V1"
    assert isinstance(order["items"][0]["tags"], list)
    assert all(entry["item"].get("parent_item_id") for entry in order["quote"]["breakup"] if entry.get("@ondc/org/title_type") == "item")
    assert all(isinstance(entry["item"].get("tags", []), list) for entry in order["quote"]["breakup"])
    fulfillment = order["fulfillments"][0]
    assert fulfillment["start"]["location"]["descriptor"]["name"]
    assert fulfillment["end"]["instructions"]["long_desc"]


def test_catalog_normalizer_supplies_bpp_descriptor_and_food_statutory_data():
    catalog = _normalize_catalog_quantities(
        {
            "bpp/providers": [
                {
                    "id": "P1",
                    "locations": [{"id": "L1"}],
                    "items": [{"id": "I1", "descriptor": {"name": "Rice"}}],
                }
            ]
        }
    )

    descriptor = catalog["bpp/descriptor"]
    assert all(descriptor[key] for key in ("name", "symbol", "short_desc", "long_desc"))
    assert isinstance(descriptor["images"], list)
    statutory = catalog["bpp/providers"][0]["items"][0]["@ondc/org/statutory_reqs_prepackaged_food"]
    assert all(isinstance(value, str) and value for value in statutory.values())
    location_range = catalog["bpp/providers"][0]["locations"][0]["time"]["range"]
    assert location_range == {"start": "0900", "end": "2100"}


def test_catalog_normalizer_emits_ret10_item_reference_fields_not_legacy_location():
    catalog = _normalize_catalog_quantities(
        {
            "bpp/providers": [
                {
                    "id": "P1",
                    "locations": [{"id": "L1"}],
                    "items": [{"id": "I1", "location": "L1", "descriptor": {"name": "Rice"}}],
                }
            ]
        }
    )

    item = catalog["bpp/providers"][0]["items"][0]
    assert item["location_id"] == "L1"
    assert "location" not in item
    assert item["parent_item_id"] == "V1"
    assert item["fulfillment_id"] == "F1"
    assert isinstance(item["tags"], list)


def test_incremental_push_mode_is_detected_and_does_not_answer_final_search():
    payload = {
        "context": {**CONTEXT, "action": "search"},
        "message": {
            "intent": {
                "tags": [{"code": "catalog_inc", "list": [{"code": "mode", "value": "start"}]}]
            }
        },
    }
    assert _is_incremental_push(payload) is True

    service = BppSearchService()
    stop_payload = {
        **payload,
        "message": {
            "intent": {
                "tags": [{"code": "catalog_inc", "list": [{"code": "mode", "value": "stop"}]}]
            }
        },
    }
    assert _is_incremental_push(stop_payload) is True
    with patch("app.ondc.bpp.services.search.bpp_client.send_callback", new_callable=AsyncMock) as callback, \
            patch("app.ondc.bpp.services.search.bpp_client.send_unsolicited", new_callable=AsyncMock) as unsolicited:
        asyncio.run(service.process_search(payload))
        asyncio.run(service.process_search(stop_payload))

    assert callback.await_count == 1
    assert unsolicited.await_count == 2


def test_quote_breakup_items_use_ret10_quote_tag_vocabulary():
    quote = build_canonical_quote([{"id": "I1", "quantity": {"count": 1}}])
    for breakup in quote["breakup"]:
        item = breakup["item"]
        assert isinstance(item["parent_item_id"], str) and item["parent_item_id"]
        assert isinstance(item["tags"], list) and item["tags"]
        assert item["tags"][0]["code"] == "quote"
        assert item["tags"][0]["list"][0]["code"] == "type"
        assert item["tags"][0]["list"][0]["value"] in {"fulfillment", "order", "item"}
        assert isinstance(item["quantity"], dict)
        assert isinstance(item["price"], dict)

        if breakup.get("@ondc/org/title_type") == "delivery":
            assert item["id"] == "F1"
            assert item["tags"][0]["list"][0]["value"] == "fulfillment"


def test_canonical_order_is_complete_for_every_order_callback_action():
    request = {
        "context": CONTEXT,
        "message": {"order": {"id": "ORDER-1", "items": [{"id": "I1"}]}},
    }
    for action in ("on_select", "on_init", "on_confirm", "on_status", "on_update", "on_cancel"):
        order = build_canonical_order(
            action=action,
            payload=request,
            state_code="Serviceable" if action in {"on_select", "on_init"} else "Pending",
            order_id="ORDER-1",
        )
        payload = {"context": {**CONTEXT, "action": action}, "message": {"order": order}}
        assert validate_ret10_payload(action, payload) == []


def test_callback_context_always_identifies_registered_bpp():
    client = BppNetworkClient()
    context = client._create_response_context(
        {**CONTEXT, "bpp_id": "workbench.ondc.tech", "bpp_uri": "https://wrong.example/ondc"},
        "on_select",
    )
    assert context["bpp_id"] == "ondc.fromnear.com"
    assert context["bpp_uri"] == "https://ondc.fromnear.com/api/v1/ondc"


def test_bpp_lookup_aliases_return_protocol_key_arrays():
    with TestClient(app) as client:
        for path in ("/lookup", "/api/v1/lookup", "/api/v1/ondc/lookup"):
            response = client.get(path)
            assert response.status_code == 200
            assert isinstance(response.json(), list)
            assert response.json()[0]["signing_public_key"]
            assert response.json()[0]["encr_public_key"]


def test_cancel_marks_lifecycle_as_cancelled_before_task_cancellation():
    tracker = LifecycleTracker()
    tracker.cancel_lifecycle_task("tx-cancel")
    assert tracker.is_cancelled("tx-cancel") is True


def test_rto_flow_is_detected_from_workbench_order_tags():
    payload = {
        "message": {
            "order": {
                "items": [{"id": "I1", "tags": [{"code": "rto_action", "list": [{"code": "action", "value": "return"}]}]}]
            }
        }
    }
    assert is_rto_flow({"transaction_id": "opaque-workbench-transaction"}, payload) is True


def test_rto_detection_does_not_classify_buyer_return_tags():
    payload = {
        "message": {
            "order": {
                "fulfillments": [{"tags": [{"code": "return_request", "list": []}]}]
            }
        }
    }
    assert is_rto_flow({"transaction_id": "opaque-workbench-transaction"}, payload) is False


def test_rto_classification_persists_after_select_marker_is_gone():
    transaction_id = "opaque-rto-transaction"
    lifecycle_tracker.mark_rto_flow(transaction_id)

    assert is_rto_flow({"transaction_id": transaction_id}, {"message": {"order": {}}}) is True
