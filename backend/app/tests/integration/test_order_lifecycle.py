import datetime
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.core.settings import settings
from app.ondc.client.http_client import ONDCResponse


def test_complete_order_lifecycle(client: TestClient):
    """Test the complete transaction lifecycle flow and callbacks."""
    # Temporarily disable signature verification for simplified payload/state testing
    with patch.object(settings, "ONDC_VERIFY_SIGNATURES", False):
        transaction_id = "lifecycle-tx-123"
        
        # ----------------------------------------------------
        # 1. SELECT FLOW
        # ----------------------------------------------------
        select_mock_response = ONDCResponse(
            status_code=200,
            json_data={"message": {"ack": {"status": "ACK"}}},
            text="ACK"
        )
        
        with patch("app.ondc.client.http_client.ondc_http_client.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = select_mock_response
            
            response = client.post(
                "/api/v1/select",
                json={
                    "transaction_id": transaction_id,
                    "bpp_id": "bpp-1",
                    "bpp_uri": "https://bpp-1.com/ondc",
                    "provider_id": "provider-1",
                    "provider_name": "Merchant Store",
                        "items": [{
                            "id": "item-1",
                            "name": "Item One",
                            "price": 150.0,
                            "quantity": 2,
                            "location_id": "L1",
                            "parent_item_id": "V1",
                            "fulfillment_id": "F1",
                        }]
                }
            )
            assert response.status_code == 200
            assert response.json()["status"] == "ACK"
            mock_post.assert_called_once()
            
        # Simulate /on_select callback from BPP
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        on_select_payload = {
            "context": {
                "action": "on_select",
                "transaction_id": transaction_id,
                "bpp_id": "bpp-1",
                "bpp_uri": "https://bpp-1.com/ondc",
                "timestamp": timestamp_str
            },
            "message": {
                "order": {
                    "provider": {"id": "provider-1"},
                    "items": [{"id": "item-1", "price": {"value": "150.0"}}],
                    "quote": {
                        "price": {"value": "300.0", "currency": "INR"},
                        "breakup": [{"title": "Item One", "price": {"value": "300.0"}}]
                    }
                }
            }
        }
        callback_res = client.post("/api/v1/ondc/on_select", json=on_select_payload)
        assert callback_res.status_code == 200
        assert callback_res.json() == {
            "context": on_select_payload["context"],
            "message": {"ack": {"status": "ACK"}}
        }
        
        # Verify order in DB has state SELECTED and amount 300.0
        check_res = client.get(f"/api/v1/orders/{transaction_id}")
        assert check_res.status_code == 200
        order_data = check_res.json()
        assert order_data["state"] == "SELECTED"
        assert order_data["amount"] == 300.0
        assert len(order_data["items"]) == 1
        assert order_data["items"][0]["price"] == 150.0

        # ----------------------------------------------------
        # 2. INIT FLOW
        # ----------------------------------------------------
        init_mock_response = ONDCResponse(
            status_code=200,
            json_data={"message": {"ack": {"status": "ACK"}}},
            text="ACK"
        )
        
        with patch("app.ondc.client.http_client.ondc_http_client.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = init_mock_response
            
            response = client.post(
                "/api/v1/init",
                json={
                    "transaction_id": transaction_id,
                    "billing_address": {
                        "name": "Jane Doe",
                        "phone": "9876543210",
                        "house": "Flat 202",
                        "street": "Rose Avenue",
                        "city": "Mumbai",
                        "state": "MH",
                        "pincode": "400001"
                    },
                    "shipping_address": {
                        "name": "Jane Doe",
                        "phone": "9876543210",
                        "house": "Flat 202",
                        "street": "Rose Avenue",
                        "city": "Mumbai",
                        "state": "MH",
                        "pincode": "400001"
                    }
                }
            )
            assert response.status_code == 200
            assert response.json()["status"] == "ACK"

            # The callback fixture below intentionally omits catalog identity
            # fields. They must still survive from select into the init wire
            # payload rather than being erased by callback persistence.
            sent_init_payload = mock_post.call_args.args[1]
            sent_init_item = sent_init_payload["message"]["order"]["items"][0]
            assert sent_init_item["location_id"] == "L1"
            assert sent_init_item["parent_item_id"] == "V1"
            assert sent_init_item["fulfillment_id"] == "F1"
            
        # Simulate /on_init callback from BPP
        on_init_payload = {
            "context": {
                "action": "on_init",
                "transaction_id": transaction_id,
                "bpp_id": "bpp-1",
                "bpp_uri": "https://bpp-1.com/ondc",
                "timestamp": timestamp_str
            },
            "message": {
                "order": {
                    "provider": {"id": "provider-1"},
                    "quote": {"price": {"value": "350.0"}}  # with delivery fees
                }
            }
        }
        callback_res = client.post("/api/v1/ondc/on_init", json=on_init_payload)
        assert callback_res.status_code == 200
        
        # Verify order in DB has state INITIALIZED and amount 350.0
        check_res = client.get(f"/api/v1/orders/{transaction_id}")
        assert check_res.status_code == 200
        assert check_res.json()["state"] == "INITIALIZED"
        assert check_res.json()["amount"] == 350.0

        # ----------------------------------------------------
        # 3. CONFIRM FLOW
        # ----------------------------------------------------
        confirm_mock_response = ONDCResponse(
            status_code=200,
            json_data={"message": {"ack": {"status": "ACK"}}},
            text="ACK"
        )
        
        with patch("app.ondc.client.http_client.ondc_http_client.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = confirm_mock_response
            
            response = client.post(
                "/api/v1/confirm",
                json={"transaction_id": transaction_id}
            )
            assert response.status_code == 200
            assert response.json()["status"] == "ACK"
            
        # Simulate /on_confirm callback from BPP
        on_confirm_payload = {
            "context": {
                "action": "on_confirm",
                "transaction_id": transaction_id,
                "bpp_id": "bpp-1",
                "bpp_uri": "https://bpp-1.com/ondc",
                "timestamp": timestamp_str
            },
            "message": {
                "order": {
                    "id": "ONDC-ORDER-999",
                    "state": "CONFIRMED",
                    "payment": {"params": {"amount": "350.0"}}
                }
            }
        }
        callback_res = client.post("/api/v1/ondc/on_confirm", json=on_confirm_payload)
        assert callback_res.status_code == 200
        
        # Verify order state is CONFIRMED and order_id is set
        check_res = client.get(f"/api/v1/orders/{transaction_id}")
        assert check_res.status_code == 200
        assert check_res.json()["state"] == "CONFIRMED"
        assert check_res.json()["order_id"] == "ONDC-ORDER-999"

        # ----------------------------------------------------
        # 4. STATUS & TRACK FLOW
        # ----------------------------------------------------
        status_mock_response = ONDCResponse(
            status_code=200,
            json_data={"message": {"ack": {"status": "ACK"}}},
            text="ACK"
        )
        
        with patch("app.ondc.client.http_client.ondc_http_client.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = status_mock_response
            
            response = client.get(f"/api/v1/status?transaction_id={transaction_id}")
            assert response.status_code == 200
            assert response.json()["order_id"] == "ONDC-ORDER-999"
            
        # Simulate /on_status callback
        on_status_payload = {
            "context": {
                "action": "on_status",
                "transaction_id": transaction_id,
                "bpp_id": "bpp-1",
                "bpp_uri": "https://bpp-1.com/ondc",
                "timestamp": timestamp_str
            },
            "message": {
                "order": {
                    "id": "ONDC-ORDER-999",
                    "state": "In-transit"
                }
            }
        }
        callback_res = client.post("/api/v1/ondc/on_status", json=on_status_payload)
        assert callback_res.status_code == 200
        
        # Verify state updated to In-transit
        check_res = client.get(f"/api/v1/orders/{transaction_id}")
        assert check_res.status_code == 200
        assert check_res.json()["state"] == "In-transit"

        # ----------------------------------------------------
        # 5. CANCEL FLOW
        # ----------------------------------------------------
        cancel_mock_response = ONDCResponse(
            status_code=200,
            json_data={"message": {"ack": {"status": "ACK"}}},
            text="ACK"
        )
        
        with patch("app.ondc.client.http_client.ondc_http_client.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = cancel_mock_response
            
            response = client.post(
                "/api/v1/cancel",
                json={
                    "transaction_id": transaction_id,
                    "cancellation_reason_id": "003"
                }
            )
            assert response.status_code == 200
            assert response.json()["status"] == "ACK"
            
        # Simulate /on_cancel callback
        on_cancel_payload = {
            "context": {
                "action": "on_cancel",
                "transaction_id": transaction_id,
                "bpp_id": "bpp-1",
                "bpp_uri": "https://bpp-1.com/ondc",
                "timestamp": timestamp_str
            },
            "message": {
                "order": {
                    "id": "ONDC-ORDER-999",
                    "state": "CANCELLED"
                }
            }
        }
        callback_res = client.post("/api/v1/ondc/on_cancel", json=on_cancel_payload)
        assert callback_res.status_code == 200
        
        # Verify state updated to CANCELLED
        check_res = client.get(f"/api/v1/orders/{transaction_id}")
        assert check_res.status_code == 200
        assert check_res.json()["state"] == "CANCELLED"
