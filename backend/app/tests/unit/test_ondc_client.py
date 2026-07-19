import pytest
import httpx
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from app.core.settings import settings
from app.ondc.client.http_client import ondc_http_client, safe_ondc_post
from app.ondc.exceptions import (
    SigningConfigurationError,
    GatewayConnectionError,
)

def test_missing_signing_key():
    """Test that http client raises SigningConfigurationError when the key is missing or is a placeholder."""
    payload = {"context": {"action": "search"}}
    
    async def run():
        # 1. Test when key is empty/missing
        with patch.object(settings, "ONDC_SIGNING_PRIVATE_KEY", ""):
            with pytest.raises(SigningConfigurationError) as exc_info:
                await ondc_http_client.post("https://example.com/search", payload, sign=True)
            assert "private key missing" in str(exc_info.value)
            
        # 2. Test when key contains a placeholder
        with patch.object(settings, "ONDC_SIGNING_PRIVATE_KEY", "INSERT_BASE64_SIGNING_PRIVATE_KEY_HERE"):
            with pytest.raises(SigningConfigurationError) as exc_info:
                await ondc_http_client.post("https://example.com/search", payload, sign=True)
            assert "private key missing" in str(exc_info.value)

    asyncio.run(run())


def test_gateway_dns_failure():
    """Test that DNS resolution failure raises GatewayConnectionError immediately without retrying."""
    payload = {"context": {"action": "search"}}
    dns_error = httpx.ConnectError("Name or service not known", request=MagicMock())
    
    async def run():
        with patch.object(ondc_http_client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = dns_error
            
            with pytest.raises(GatewayConnectionError) as exc_info:
                await ondc_http_client.post("https://staging.gateway.ondc.org/search", payload, sign=False, retries=3)
                
            assert exc_info.value.status_code == 502
            assert exc_info.value.reason == "DNS resolution failed"
            assert exc_info.value.gateway == "https://staging.gateway.ondc.org/search"
            assert mock_post.call_count == 1

    asyncio.run(run())


def test_gateway_timeout():
    """Test that gateway timeout retries and eventually raises GatewayConnectionError with 504."""
    payload = {"context": {"action": "search"}}
    timeout_error = httpx.TimeoutException("Connection timed out", request=MagicMock())
    
    async def run():
        with patch.object(ondc_http_client.client, "post", new_callable=AsyncMock) as mock_post, \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_post.side_effect = timeout_error
            
            with pytest.raises(GatewayConnectionError) as exc_info:
                await ondc_http_client.post("https://example.com/search", payload, sign=False, retries=3)
                
            assert exc_info.value.status_code == 504
            assert exc_info.value.reason == "Timeout"
            assert mock_post.call_count == 3
            assert mock_sleep.call_count == 2

    asyncio.run(run())


def test_invalid_gateway_url():
    """Test that an invalid URL schema raises GatewayConnectionError immediately."""
    payload = {"context": {"action": "search"}}
    url_error = httpx.UnsupportedProtocol("Unsupported protocol", request=MagicMock())
    
    async def run():
        with patch.object(ondc_http_client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = url_error
            
            with pytest.raises(GatewayConnectionError) as exc_info:
                await ondc_http_client.post("invalid_url", payload, sign=False, retries=3)
                
            assert exc_info.value.status_code == 502
            assert "Malformed URL" in exc_info.value.reason
            assert mock_post.call_count == 1

    asyncio.run(run())


def test_retry_logic_success():
    """Test that transient network errors are retried and can succeed on subsequent attempts."""
    payload = {"context": {"action": "search"}}
    transient_error = httpx.ConnectError("Connection timed out or reset", request=MagicMock())
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"message": {"ack": {"status": "ACK"}}}
    mock_response.text = "ACK"
    
    async def run():
        with patch.object(ondc_http_client.client, "post", new_callable=AsyncMock) as mock_post, \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_post.side_effect = [transient_error, transient_error, mock_response]
            
            response = await ondc_http_client.post("https://example.com/search", payload, sign=False, retries=3)
            
            assert response.status_code == 200
            assert response.json_data == {"message": {"ack": {"status": "ACK"}}}
            assert mock_post.call_count == 3
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(0.5)
            mock_sleep.assert_any_call(1.0)

    asyncio.run(run())


def test_gateway_error_non_2xx():
    """Test that gateway non-2xx error codes raise GatewayConnectionError with details."""
    payload = {"context": {"action": "search"}}
    
    async def run():
        # Test HTTP 400
        mock_response_400 = MagicMock(spec=httpx.Response)
        mock_response_400.status_code = 400
        mock_response_400.headers = {"content-type": "application/json"}
        mock_response_400.text = '{"error": "bad request"}'
        
        with patch.object(ondc_http_client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response_400
            with pytest.raises(GatewayConnectionError) as exc_info:
                await ondc_http_client.post("https://example.com/search", payload, sign=False, retries=1)
            assert exc_info.value.status_code == 400
            assert exc_info.value.response_body == '{"error": "bad request"}'

        # Test HTTP 401
        mock_response_401 = MagicMock(spec=httpx.Response)
        mock_response_401.status_code = 401
        mock_response_401.headers = {"content-type": "text/plain"}
        mock_response_401.text = "Unauthorized"
        
        with patch.object(ondc_http_client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response_401
            with pytest.raises(GatewayConnectionError) as exc_info:
                await ondc_http_client.post("https://example.com/search", payload, sign=False, retries=1)
            assert exc_info.value.status_code == 401
            assert exc_info.value.response_body == "Unauthorized"

        # Test HTTP 500 after retries
        mock_response_500 = MagicMock(spec=httpx.Response)
        mock_response_500.status_code = 500
        mock_response_500.headers = {"content-type": "application/json"}
        mock_response_500.text = '{"error": "internal error"}'
        
        with patch.object(ondc_http_client.client, "post", new_callable=AsyncMock) as mock_post, \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_post.return_value = mock_response_500
            with pytest.raises(GatewayConnectionError) as exc_info:
                await ondc_http_client.post("https://example.com/search", payload, sign=False, retries=2)
            assert exc_info.value.status_code == 500
            assert exc_info.value.response_body == '{"error": "internal error"}'
            assert mock_post.call_count == 2

    asyncio.run(run())


def test_safe_ondc_post_success():
    """Test that safe_ondc_post returns ACK for successful ONDC requests."""
    payload = {"context": {"action": "search"}}
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"message": {"ack": {"status": "ACK"}}}
    mock_response.text = "ACK"
    
    async def run():
        with patch.object(ondc_http_client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await safe_ondc_post(
                url="https://example.com/search",
                payload=payload,
                transaction_id="tx_123",
                message_id="msg_456",
                sign=False
            )
            assert result == {
                "transaction_id": "tx_123",
                "message_id": "msg_456",
                "status": "ACK"
            }

    asyncio.run(run())


def test_safe_ondc_post_non_2xx():
    """Test that safe_ondc_post catches GatewayConnectionError and returns structured gateway error details."""
    payload = {"context": {"action": "search"}}
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 400
    mock_response.headers = {"content-type": "application/json"}
    mock_response.text = '{"error": "bad request"}'
    
    async def run():
        with patch.object(ondc_http_client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await safe_ondc_post(
                url="https://example.com/search",
                payload=payload,
                transaction_id="tx_123",
                message_id="msg_456",
                sign=False
            )
            assert result == {
                "transaction_id": "tx_123",
                "message_id": "msg_456",
                "status": "GATEWAY_ERROR",
                "gateway_status_code": 400,
                "gateway_response": '{"error": "bad request"}'
            }

    asyncio.run(run())


def test_safe_ondc_post_connection_error():
    """Test that safe_ondc_post handles connection errors and DNS resolution failure by returning structured error info."""
    payload = {"context": {"action": "search"}}
    dns_error = httpx.ConnectError("Name or service not known", request=MagicMock())
    
    async def run():
        with patch.object(ondc_http_client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = dns_error
            result = await safe_ondc_post(
                url="https://example.com/search",
                payload=payload,
                transaction_id="tx_123",
                message_id="msg_456",
                sign=False,
                retries=1
            )
            assert result["transaction_id"] == "tx_123"
            assert result["message_id"] == "msg_456"
            assert result["status"] == "GATEWAY_ERROR"
            assert result["error_type"] == "ConnectError"
            assert "Name or service not known" in result["error_message"]

    asyncio.run(run())
