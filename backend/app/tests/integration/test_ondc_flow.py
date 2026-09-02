import gzip
import json
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.core.settings import settings
from app.ondc.client.http_client import ONDCResponse
from app.ondc.crypto.utils import generate_auth_header


def test_initiate_search_success(client: TestClient):
    """Test that POST /api/v1/search successfully triggers broadcast to gateway."""
    mock_response = ONDCResponse(
        status_code=200,
        json_data={"message": {"ack": {"status": "ACK"}}},
        text="ACK"
    )
    
    with patch("app.ondc.client.http_client.ondc_http_client.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        response = client.post(
            "/api/v1/search",
            json={"query": "organic coffee"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "transaction_id" in data
        assert "message_id" in data
        assert data["status"] == "ACK"
        
        # Verify the client POST call was made to the gateway with signed header
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "/search" in args[0]
        assert kwargs.get("sign") is True


def test_on_search_callback_and_results(client: TestClient):
    """Test on_search callback stores results and GET /results returns mapped internal ProductModel list."""
    # Temporarily disable signature verification for simple DB insertion path testing
    with patch.object(settings, "ONDC_VERIFY_SIGNATURES", False):
        transaction_id = "integration-test-tx-uuid"
        message_id = "integration-test-msg-uuid"
        
        import datetime
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        
        callback_payload = {
            "context": {
                "domain": settings.ONDC_DOMAIN,
                "country": settings.ONDC_COUNTRY,
                "city": settings.ONDC_CITY,
                "action": "on_search",
                "core_version": "1.2.0",
                "bap_id": settings.ONDC_SUBSCRIBER_ID,
                "bap_uri": settings.ONDC_SUBSCRIBER_URI,
                "bpp_id": "bpp-merchant-1",
                "bpp_uri": "https://bpp-merchant-1.com/ondc",
                "transaction_id": transaction_id,
                "message_id": message_id,
                "timestamp": timestamp_str
            },
            "message": {
                "catalog": {
                    "bpp/providers": [
                        {
                            "id": "provider-merchant-1",
                            "descriptor": {
                                "name": "Organic Merchant Store"
                            },
                            "items": [
                                {
                                    "id": "item-coffee-beans",
                                    "location_id": "L1",
                                    "parent_item_id": "V1",
                                    "fulfillment_id": "F1",
                                    "tags": [],
                                    "descriptor": {
                                        "name": "Organic Coffee Beans 500g",
                                        "short_desc": "Medium roast premium beans",
                                        "images": ["https://img.com/coffee-beans.png"]
                                    },
                                    "price": {
                                        "value": "450.00",
                                        "currency": "INR"
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        }
        
        # 1. Trigger the on_search callback
        callback_response = client.post(
            "/api/v1/ondc/on_search",
            json=callback_payload
        )
        assert callback_response.status_code == 200
        assert callback_response.json() == {
            "context": callback_payload["context"],
            "message": {"ack": {"status": "ACK"}}
        }
        
        # 2. Query the results endpoint using the same transaction ID
        results_response = client.get(
            f"/api/v1/search/results?transaction_id={transaction_id}"
        )
        assert results_response.status_code == 200
        results_data = results_response.json()
        assert len(results_data) == 1
        
        product = results_data[0]
        assert product["id"] == "item-coffee-beans"
        assert product["name"] == "Organic Coffee Beans 500g"
        assert product["description"] == "Medium roast premium beans"
        assert product["price"] == 450.0
        assert product["currency"] == "INR"
        assert product["images"] == ["https://img.com/coffee-beans.png"]
        assert product["provider_id"] == "provider-merchant-1"
        assert product["provider_name"] == "Organic Merchant Store"
        assert product["bpp_id"] == "bpp-merchant-1"
        assert product["transaction_id"] == transaction_id
        assert product["location_id"] == "L1"
        assert product["parent_item_id"] == "V1"
        assert product["fulfillment_id"] == "F1"
        assert product["tags"] == []


def test_on_search_callback_decodes_gzip_body(client: TestClient):
    """Accept gateway callbacks that use HTTP gzip content encoding."""
    with patch.object(settings, "ONDC_VERIFY_SIGNATURES", False):
        import datetime

        callback_payload = {
            "context": {
                "domain": settings.ONDC_DOMAIN,
                "country": settings.ONDC_COUNTRY,
                "city": settings.ONDC_CITY,
                "action": "on_search",
                "core_version": "1.2.0",
                "bap_id": settings.ONDC_SUBSCRIBER_ID,
                "bap_uri": settings.ONDC_SUBSCRIBER_URI,
                "bpp_id": "gzip-bpp",
                "bpp_uri": "https://gzip-bpp.example/ondc",
                "transaction_id": "gzip-callback-tx",
                "message_id": "gzip-callback-msg",
                "timestamp": datetime.datetime.now(datetime.timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            },
            "message": {"catalog": {"bpp/providers": []}},
        }
        body_bytes = json.dumps(callback_payload, separators=(",", ":")).encode("utf-8")

        response = client.post(
            "/api/v1/ondc/on_search",
            content=gzip.compress(body_bytes),
            headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "context": callback_payload["context"],
            "message": {"ack": {"status": "ACK"}},
        }


def test_on_search_callback_signature_failure(client: TestClient):
    """Test on_search callback returns 401/NACK when signature verification is enabled but invalid."""
    with patch.object(settings, "ONDC_VERIFY_SIGNATURES", True):
        transaction_id = "sig-fail-tx-uuid"
        message_id = "sig-fail-msg-uuid"
        
        import datetime
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        
        callback_payload = {
            "context": {
                "domain": settings.ONDC_DOMAIN,
                "country": settings.ONDC_COUNTRY,
                "city": settings.ONDC_CITY,
                "action": "on_search",
                "core_version": "1.2.0",
                "bap_id": settings.ONDC_SUBSCRIBER_ID,
                "bap_uri": settings.ONDC_SUBSCRIBER_URI,
                "bpp_id": "bpp-merchant-1",
                "bpp_uri": "https://bpp-merchant-1.com/ondc",
                "transaction_id": transaction_id,
                "message_id": message_id,
                "timestamp": timestamp_str
            },
            "message": {
                "catalog": {"bpp/providers": []}
            }
        }
        
        # Send post with headers but invalid signature value
        headers = {"Authorization": "Signature keyId=\"bpp-merchant-1|bap-unique-key-id|ed25519\",algorithm=\"ed25519\",created=\"1694952000\",expires=\"1694952300\",headers=\"(created) (expires) digest\",signature=\"invalidsignaturebytesbase64=\""}
        
        response = client.post(
            "/api/v1/ondc/on_search",
            json=callback_payload,
            headers=headers
        )
        assert response.status_code == 401
        data = response.json()
        assert data["message"]["ack"]["status"] == "NACK"
        assert "Signature verification failed" in data["error"]["message"]


def test_on_search_callback_signature_success(client: TestClient):
    """Test on_search callback succeeds when valid signature matches lookups."""
    with patch.object(settings, "ONDC_VERIFY_SIGNATURES", True):
        # We need registry lookup to return our public key for the mock BPP sender
        # so verification resolves the correct public key to match the signature we generate.
        mock_registry_data = [
            {
                "subscriber_id": "bpp-merchant-test",
                "type": "BPP",
                "domain": settings.ONDC_DOMAIN,
                "unique_key_id": "bpp-key-id",
                "signing_public_key": settings.ONDC_SIGNING_PUBLIC_KEY,
                "enc_public_key": settings.ONDC_ENC_PUBLIC_KEY,
                "subscriber_url": "https://bpp-merchant-test.com/ondc",
                "status": "SUBSCRIBED",
            }
        ]
        
        with patch("app.ondc.validators.protocol.registry_client.lookup", new_callable=AsyncMock) as mock_lookup:
            mock_lookup.return_value = mock_registry_data
            
            transaction_id = "sig-success-tx-uuid"
            message_id = "sig-success-msg-uuid"
            
            import datetime
            timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
            
            callback_payload = {
                "context": {
                    "domain": settings.ONDC_DOMAIN,
                    "country": settings.ONDC_COUNTRY,
                    "city": settings.ONDC_CITY,
                    "action": "on_search",
                    "core_version": "1.2.0",
                    "bap_id": settings.ONDC_SUBSCRIBER_ID,
                    "bap_uri": settings.ONDC_SUBSCRIBER_URI,
                    "bpp_id": "bpp-merchant-test",
                    "bpp_uri": "https://bpp-merchant-test.com/ondc",
                    "transaction_id": transaction_id,
                    "message_id": message_id,
                    "timestamp": timestamp_str
                },
                "message": {
                    "catalog": {"bpp/providers": []}
                }
            }
            
            # Generate valid signature header for this exact body content
            import json
            body_bytes = json.dumps(callback_payload, separators=(',', ':')).encode("utf-8")
            valid_auth_header = generate_auth_header(
                body=body_bytes,
                subscriber_id="bpp-merchant-test",
                unique_key_id="bpp-key-id",
                private_key_str=settings.ONDC_SIGNING_PRIVATE_KEY
            )
            
            headers = {
                "Authorization": valid_auth_header,
                "Content-Type": "application/json"
            }
            response = client.post(
                "/api/v1/ondc/on_search",
                content=body_bytes,
                headers=headers
            )
            assert response.status_code == 200
            assert response.json() == {
                "context": callback_payload["context"],
                "message": {"ack": {"status": "ACK"}}
            }
