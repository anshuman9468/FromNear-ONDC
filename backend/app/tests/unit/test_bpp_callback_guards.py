from fastapi.testclient import TestClient

from app.main import app
from app.ondc.bpp.client import BppNetworkClient
from app.ondc.bpp.order_builder import build_canonical_order, build_canonical_quote, validate_ret10_payload
from app.ondc.bpp.services.search import _normalize_catalog_quantities
from app.ondc.bpp.state_machine import LifecycleTracker


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
    assert all(entry["item"]["parent_item_id"] for entry in order["quote"]["breakup"])
    assert all(isinstance(entry["item"]["tags"], list) for entry in order["quote"]["breakup"])
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


def test_quote_breakup_items_use_ret10_item_tag_vocabulary():
    quote = build_canonical_quote([{"id": "I1", "quantity": {"count": 1}}])
    for breakup in quote["breakup"]:
        item = breakup["item"]
        assert isinstance(item["parent_item_id"], str) and item["parent_item_id"]
        assert isinstance(item["tags"], list) and item["tags"]
        assert item["tags"][0]["code"] == "type"
        assert item["tags"][0]["list"][0]["code"] == "type"
        assert item["tags"][0]["list"][0]["value"] in {"fulfillment", "order", "item"}


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
