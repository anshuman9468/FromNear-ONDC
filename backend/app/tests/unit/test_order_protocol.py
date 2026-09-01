import pytest
from app.ondc.protocol.builders import (
    SelectRequestBuilder,
    InitRequestBuilder,
    ConfirmRequestBuilder,
    StatusRequestBuilder,
    TrackRequestBuilder,
    CancelRequestBuilder,
    SupportRequestBuilder,
    UpdateRequestBuilder,
)
from app.ondc.protocol.parsers import (
    SelectResponse,
    InitResponse,
    ConfirmResponse,
    StatusResponse,
    TrackResponse,
    CancelResponse,
    SupportResponse,
)


def test_select_request_builder_normalizes_workbench_items():
    payload = SelectRequestBuilder.build(
        transaction_id="tx-123",
        message_id="msg-123",
        bpp_id="bpp-1",
        bpp_uri="https://bpp-1.com",
        provider_id="provider-1",
        # This is the legacy shape emitted by the Workbench input form.
        items=[
            {"id": "I1", "location": "L1", "quantity": 2},
            {"id": "I2", "location": "L1", "quantity": {"count": 1}},
        ],
    )
    assert payload["context"]["action"] == "select"
    assert payload["context"]["transaction_id"] == "tx-123"
    assert payload["context"]["bpp_id"] == "bpp-1"
    assert payload["message"]["order"]["provider"]["id"] == "provider-1"
    for expected_id, expected_count, item in zip(
        ("I1", "I2"),
        (2, 1),
        payload["message"]["order"]["items"],
    ):
        assert item["id"] == expected_id
        assert item["location_id"] == "L1"
        assert "location" not in item
        assert item["fulfillment_id"] == "F1"
        assert item["parent_item_id"] == "V1"
        assert item["quantity"] == {"count": expected_count}
        assert item["tags"] == [{"code": "type", "list": [{"code": "type", "value": "item"}]}]


def test_init_request_builder():
    billing = {"name": "John", "phone": "123", "house": "1A", "street": "Road", "city": "Bangalore", "state": "KA", "pincode": "560001"}
    shipping = {"name": "John", "phone": "123", "house": "1A", "street": "Road", "city": "Bangalore", "state": "KA", "pincode": "560001"}
    payload = InitRequestBuilder.build(
        transaction_id="tx-123",
        message_id="msg-123",
        bpp_id="bpp-1",
        bpp_uri="https://bpp-1.com",
        provider_id="provider-1",
        items=[{"id": "item-1", "quantity": 2}],
        billing_address=billing,
        shipping_address=shipping,
    )
    assert payload["context"]["action"] == "init"
    assert payload["message"]["order"]["billing"]["name"] == "John"
    assert payload["message"]["order"]["fulfillments"][0]["end"]["contact"]["name"] == "John"


def test_confirm_request_builder():
    billing = {"name": "John", "phone": "123", "house": "1A", "street": "Road", "city": "Bangalore", "state": "KA", "pincode": "560001"}
    shipping = {"name": "John", "phone": "123", "house": "1A", "street": "Road", "city": "Bangalore", "state": "KA", "pincode": "560001"}
    payload = ConfirmRequestBuilder.build(
        transaction_id="tx-123",
        message_id="msg-123",
        bpp_id="bpp-1",
        bpp_uri="https://bpp-1.com",
        provider_id="provider-1",
        items=[
            {"id": "I1", "location": "L1", "quantity": 2},
            {"id": "I2", "location": "L1", "quantity": 1},
        ],
        billing_address=billing,
        shipping_address=shipping,
        amount=450.0,
    )
    assert payload["context"]["action"] == "confirm"
    assert payload["message"]["order"]["payment"]["params"]["amount"] == "450.0"
    for item in payload["message"]["order"]["items"]:
        assert item["location_id"] == "L1"
        assert "location" not in item
        assert item["parent_item_id"] == "V1"
        assert item["tags"]


def test_status_request_builder():
    payload = StatusRequestBuilder.build(
        transaction_id="tx-123",
        message_id="msg-123",
        bpp_id="bpp-1",
        bpp_uri="https://bpp-1.com",
        order_id="order-123",
    )
    assert payload["context"]["action"] == "status"
    assert payload["message"]["order_id"] == "order-123"


def test_track_request_builder():
    payload = TrackRequestBuilder.build(
        transaction_id="tx-123",
        message_id="msg-123",
        bpp_id="bpp-1",
        bpp_uri="https://bpp-1.com",
        order_id="order-123",
    )
    assert payload["context"]["action"] == "track"
    assert payload["message"]["order_id"] == "order-123"


def test_cancel_request_builder():
    payload = CancelRequestBuilder.build(
        transaction_id="tx-123",
        message_id="msg-123",
        bpp_id="bpp-1",
        bpp_uri="https://bpp-1.com",
        order_id="order-123",
        cancellation_reason_id="001",
    )
    assert payload["context"]["action"] == "cancel"
    assert payload["message"]["order_id"] == "order-123"
    assert payload["message"]["cancellation_reason_id"] == "001"


def test_support_request_builder():
    payload = SupportRequestBuilder.build(
        transaction_id="tx-123",
        message_id="msg-123",
        bpp_id="bpp-1",
        bpp_uri="https://bpp-1.com",
        ref_id="ref-123",
    )
    assert payload["context"]["action"] == "support"
    assert payload["message"]["ref_id"] == "ref-123"


@pytest.mark.parametrize("update_target", ["item", "fulfillment"])
def test_update_request_builder_never_emits_empty_fulfillments(update_target):
    payload = UpdateRequestBuilder.build(
        transaction_id="tx-123",
        message_id="msg-123",
        bpp_id="bpp-1",
        bpp_uri="https://bpp-1.com",
        order_id="order-123",
        update_target=update_target,
        order={"id": "order-123", "items": [{"id": "I1"}], "fulfillments": []},
    )

    fulfillments = payload["message"]["order"]["fulfillments"]
    assert len(fulfillments) >= 1
    assert fulfillments[0]["id"] == "F1"
    assert fulfillments[0]["type"] in {"Delivery", "Return"}
    assert isinstance(fulfillments[0]["tags"], list)


def test_select_response_parser():
    payload = {
        "context": {"transaction_id": "tx-123", "bpp_id": "bpp-1"},
        "message": {
            "order": {
                "provider": {"id": "provider-1"},
                "items": [{"id": "item-1"}],
                "quote": {"price": {"value": "99.90"}}
            }
        }
    }
    parser = SelectResponse(payload)
    assert parser.is_success is True
    assert parser.transaction_id == "tx-123"
    assert parser.quote_price == 99.90
    assert parser.provider_id == "provider-1"
    assert parser.items[0]["id"] == "item-1"


def test_confirm_response_parser():
    payload = {
        "context": {"transaction_id": "tx-123"},
        "message": {
            "order": {
                "id": "order-123",
                "state": "CONFIRMED",
                "payment": {"params": {"amount": "450.0"}}
            }
        }
    }
    parser = ConfirmResponse(payload)
    assert parser.is_success is True
    assert parser.order_id == "order-123"
    assert parser.state == "CONFIRMED"
    assert parser.total_amount == 450.0
