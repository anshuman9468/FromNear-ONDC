import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from app.ondc.services.diagnostics import _bpp_crypto_config, validate_search_payload, run_diagnostics
from app.core.settings import settings

def test_validate_search_payload_valid():
    """Test that a valid payload returns no schema validation errors."""
    payload = {
        "context": {
            "domain": "nic2004:52110",
            "country": "IND",
            "city": "std:080",
            "action": "search",
            "core_version": "1.2.0",
            "bap_id": "ondc.fromnear.com",
            "bap_uri": "https://ondc.fromnear.app/api",
            "transaction_id": "tx-123",
            "message_id": "msg-456",
            "timestamp": "2026-07-17T18:00:00.000Z",
            "ttl": "PT30S"
        },
        "message": {
            "intent": {
                "item": {
                    "descriptor": {
                        "name": "test product"
                    }
                }
            }
        }
    }
    
    # Mock settings to match the payload values
    with patch("app.ondc.services.diagnostics.settings") as mock_settings:
        mock_settings.ONDC_DOMAIN = "nic2004:52110"
        mock_settings.ONDC_SUBSCRIBER_ID = "ondc.fromnear.com"
        mock_settings.ONDC_SUBSCRIBER_URI = "https://ondc.fromnear.app/api"
        mock_settings.ONDC_VERSION = "1.2.0"
        mock_settings.ONDC_COUNTRY = "IND"
        mock_settings.ONDC_CITY = "std:080"
        
        errors = validate_search_payload(payload)
        assert len(errors) == 0

def test_validate_search_payload_invalid():
    """Test that schema validation catches missing or mismatched fields."""
    payload = {
        "context": {
            "domain": "wrong-domain",
            "action": "select",  # Must be search
            "core_version": "1.1.0"
        }
    }
    
    with patch("app.ondc.services.diagnostics.settings") as mock_settings:
        mock_settings.ONDC_DOMAIN = "nic2004:52110"
        mock_settings.ONDC_SUBSCRIBER_ID = "ondc.fromnear.com"
        mock_settings.ONDC_SUBSCRIBER_URI = "https://ondc.fromnear.app/api"
        mock_settings.ONDC_VERSION = "1.2.0"
        
        errors = validate_search_payload(payload)
        assert len(errors) > 0
        err_str = " ".join(errors)
        assert "domain" in err_str
        assert "must be 'search'" in err_str
        assert "core_version" in err_str
        assert "Missing required root key: 'message'" in err_str


def test_diagnostics_prefers_registered_bpp_credentials_when_available():
    with patch.object(settings, "ONDC_BPP_SIGNING_PRIVATE_KEY", "seller-private"), \
         patch.object(settings, "ONDC_BPP_SIGNING_PUBLIC_KEY", "seller-public"), \
         patch.object(settings, "ONDC_BPP_ENC_PUBLIC_KEY", "seller-encryption-public"), \
         patch.object(settings, "ONDC_BPP_UNIQUE_KEY_ID", "seller-key-id"):
        crypto = _bpp_crypto_config()

    assert crypto["type"] == "BPP"
    assert crypto["unique_key_id"] == "seller-key-id"
    assert crypto["public_key"] == "seller-public"
    assert crypto["encryption_public_key"] == "seller-encryption-public"

def test_run_diagnostics_flow():
    """Test that run_diagnostics executes all modules and compiles a report."""
    async def run():
        with patch.object(settings, "ONDC_BPP_SIGNING_PRIVATE_KEY", "seller-private"), \
             patch.object(settings, "ONDC_BPP_SIGNING_PUBLIC_KEY", "ZGVyaXZlZC1rZXktYnl0ZXM="), \
             patch.object(settings, "ONDC_BPP_ENC_PUBLIC_KEY", "seller-encryption-public"), \
             patch.object(settings, "ONDC_BPP_UNIQUE_KEY_ID", "seller-key-id"), \
             patch("app.ondc.services.diagnostics.load_private_key") as mock_load_priv, \
             patch("app.ondc.services.diagnostics.generate_auth_header", return_value="Signature header") as mock_gen, \
             patch("app.ondc.services.diagnostics.parse_auth_header") as mock_parse, \
             patch("httpx.AsyncClient.post") as mock_post, \
             patch("httpx.AsyncClient.get") as mock_get, \
             patch("socket.gethostbyname", return_value="127.0.0.1"), \
             patch("ssl.create_default_context"):
             
            # Mock private key derivation
            mock_priv_instance = MagicMock()
            mock_pub_instance = MagicMock()
            mock_pub_instance.public_bytes.return_value = b"derived-key-bytes"
            mock_priv_instance.public_key.return_value = mock_pub_instance
            mock_load_priv.return_value = mock_priv_instance
            
            mock_parse.return_value = {
                "created": "123", "expires": "456", "keyId": "key",
                "digest": "dig", "signature": "sig", "algorithm": "ed25519"
            }
            
            # Mock registry lookup and gateway responses
            mock_registry_res = MagicMock()
            mock_registry_res.status_code = 200
            mock_registry_res.headers = {"content-type": "application/json"}
            mock_registry_res.json.return_value = [
                {
                    "subscriber_id": settings.ONDC_SUBSCRIBER_ID,
                    "status": "SUBSCRIBED",
                    "ukId": "seller-key-id",
                    "signing_public_key": "ZGVyaXZlZC1rZXktYnl0ZXM=",
                    "enc_public_key": "seller-encryption-public",
                    "subscriber_url": settings.ONDC_SUBSCRIBER_URI
                }
            ]
            mock_registry_res.text = "[]"
            
            mock_gateway_res = MagicMock()
            mock_gateway_res.status_code = 200
            mock_gateway_res.headers = {"content-type": "application/json"}
            mock_gateway_res.text = "ACK"
            
            mock_post.side_effect = [mock_registry_res, mock_gateway_res]
            
            mock_get_res = MagicMock()
            mock_get_res.status_code = 200
            mock_get_res.headers = {}
            mock_get.return_value = mock_get_res

            # Run diagnostics logic
            report = await run_diagnostics()
            
            assert "configuration" in report
            assert "registry" in report
            assert "gateway" in report
            assert "details" in report
            assert "recommendations" in report
            assert report["details"]["configuration"]["values"]["active_credential_set"] == "BPP"
            assert mock_gen.call_count >= 2
            assert all(call.kwargs["unique_key_id"] == "seller-key-id" for call in mock_gen.call_args_list)
            lookup_payload = mock_post.call_args_list[0].kwargs["content"]
            assert b'"ukId":"seller-key-id"' in lookup_payload
            assert b'"country":"IND"' in lookup_payload
            assert b'"city":"std:080"' in lookup_payload
            assert report["details"]["payload"]["validated_payload"]["message"]["intent"]["payment"] == {
                "@ondc/org/buyer_app_finder_fee_type": "percent",
                "@ondc/org/buyer_app_finder_fee_amount": "3",
            }

    asyncio.run(run())
