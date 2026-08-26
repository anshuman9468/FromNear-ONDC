import time
import json
import logging
import asyncio
import httpx
from typing import Dict, Any, Optional
from app.core.settings import settings
from app.core.logging import correlation_id_ctx
from app.ondc.crypto.utils import generate_auth_header
from app.ondc.exceptions import (
    SigningConfigurationError,
    GatewayConnectionError,
    SignatureGenerationError,
)

logger = logging.getLogger(__name__)


class ONDCResponse:
    def __init__(self, status_code: int, json_data: Optional[Dict[str, Any]], text: str):
        self.status_code = status_code
        self.json_data = json_data
        self.text = text

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> Optional[Dict[str, Any]]:
        return self.json_data


class ONDCHttpClient:
    def __init__(self):
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=50)
        timeout = httpx.Timeout(15.0, connect=5.0)
        self.client = httpx.AsyncClient(limits=limits, timeout=timeout)

    async def close(self) -> None:
        await self.client.aclose()

    async def post(
        self,
        url: str,
        payload: Dict[str, Any],
        sign: bool = True,
        headers: Optional[Dict[str, str]] = None,
        retries: int = 3,
        subscriber_id: Optional[str] = None,
        unique_key_id: Optional[str] = None,
        private_key_str: Optional[str] = None,
    ) -> ONDCResponse:
        """Send a signed POST request to an ONDC participant or gateway."""
        headers = headers or {}
        headers["Content-Type"] = "application/json"
        
        # Propagate X-Correlation-ID
        corr_id = correlation_id_ctx.get()
        if corr_id:
            headers["X-Correlation-ID"] = corr_id
            
        body_bytes = json.dumps(payload).encode("utf-8")
        
        # Automatically sign the payload if requested
        if sign:
            private_key = private_key_str or settings.ONDC_SIGNING_PRIVATE_KEY
            if not private_key or private_key.strip() == "" or "INSERT_" in private_key:
                logger.error("ONDC signing private key is missing or not configured.")
                raise SigningConfigurationError(
                    "ONDC signing key not configured: Ed25519 private key missing"
                )
            try:
                auth_header = generate_auth_header(
                    body_bytes,
                    subscriber_id=subscriber_id,
                    unique_key_id=unique_key_id,
                    private_key_str=private_key,
                )
                headers["Authorization"] = auth_header
            except ValueError as val_err:
                logger.error(f"ONDC signing private key could not be loaded: {str(val_err)}")
                raise SigningConfigurationError(
                    f"ONDC signing key format invalid: {str(val_err)}"
                )
            except Exception as e:
                logger.error(f"Failed to generate ONDC Auth header: {str(e)}", exc_info=True)
                raise SignatureGenerationError(f"Signature generation failed: {str(e)}")
                
        # Structured logging data
        transaction_id = payload.get("context", {}).get("transaction_id", "N/A")
        message_id = payload.get("context", {}).get("message_id", "N/A")
        action = payload.get("context", {}).get("action", "N/A")
        
        response = None
        for attempt in range(1, retries + 1):
            start_time = time.time()
            auth_header_exists = "Authorization" in headers
            
            logger.info(
                f"Sending ONDC POST request: {action} to {url} (Attempt {attempt}/{retries})\n"
                f"  Gateway URL: {url}\n"
                f"  Action: {action}\n"
                f"  Transaction ID: {transaction_id}\n"
                f"  Message ID: {message_id}\n"
                f"  Correlation ID: {corr_id or 'None'}\n"
                f"  Signing Enabled: {sign}\n"
                f"  Authorization Header Generated: {auth_header_exists}",
                extra={
                    "correlation_id": corr_id,
                    "transaction_id": transaction_id,
                    "message_id": message_id,
                    "action": action,
                    "attempt": attempt,
                    "gateway_url": url,
                    "signing_enabled": sign,
                    "auth_header_success": auth_header_exists,
                }
            )
            
            try:
                res = await self.client.post(url, content=body_bytes, headers=headers)
                latency = time.time() - start_time
                
                # Retrieve JSON if present
                res_json = None
                if res.headers.get("content-type", "").startswith("application/json"):
                    try:
                        res_json = res.json()
                    except Exception:
                        pass
                
                response = ONDCResponse(
                    status_code=res.status_code,
                    json_data=res_json,
                    text=res.text
                )
                
                # Detailed structured logging of outbound request and response details
                logger.info(
                    f"ONDC HTTP Outbound Request/Response Log:\n"
                    f"  Request URL: {url}\n"
                    f"  HTTP Method: POST\n"
                    f"  HTTP Status Code: {res.status_code}\n"
                    f"  Response Headers: {dict(res.headers)}\n"
                    f"  Raw Response Body: {res.text}"
                )
                
                # Log non-2xx complete response body before any parsing
                if not (200 <= res.status_code < 300):
                    logger.error(
                        f"Non-2xx response from ONDC Gateway/BPP:\n"
                        f"  Request URL: {url}\n"
                        f"  HTTP Method: POST\n"
                        f"  HTTP Status Code: {res.status_code}\n"
                        f"  Raw Response Body: {res.text}"
                    )
                
                # Retry on 5xx or transient errors, raise immediately on 4xx
                if res.status_code < 500:
                    if not (200 <= res.status_code < 300):
                        raise GatewayConnectionError(
                            message="ONDC Gateway returned an error response",
                            gateway=url,
                            reason=f"HTTP {res.status_code}",
                            status_code=res.status_code,
                            response_body=res.text
                        )
                    return response
                    
            except httpx.RequestError as e:
                latency = time.time() - start_time
                exc_str = str(e).lower()
                
                # Check for DNS/name resolution errors or malformed URL
                is_dns = False
                is_unsupported = isinstance(e, (httpx.UnsupportedProtocol, httpx.InvalidURL))
                
                if isinstance(e, httpx.ConnectError):
                    if any(term in exc_str for term in [
                        "name or service not known",
                        "temporary failure in name resolution",
                        "nodename nor servname",
                        "getaddrinfo failed",
                        "gai_error",
                        "dns resolution failed"
                    ]):
                        is_dns = True
                
                logger.warning(
                    f"ONDC POST request failed with network error on attempt {attempt}: {str(e)}",
                    exc_info=True,
                    extra={
                        "correlation_id": corr_id,
                        "transaction_id": transaction_id,
                        "message_id": message_id,
                        "latency_seconds": latency,
                    }
                )
                
                # If non-retryable (DNS failure or invalid URL), raise immediately
                if is_dns or is_unsupported:
                    reason_msg = "DNS resolution failed" if is_dns else "Malformed URL or unsupported protocol"
                    raise GatewayConnectionError(
                        message="Unable to reach ONDC Gateway",
                        gateway=url,
                        reason=reason_msg,
                        status_code=502,
                        error_type=type(e).__name__,
                        error_message=str(e)
                    )
                
                # If we exhausted all retries, raise GatewayConnectionError
                if attempt == retries:
                    reason_msg = "Timeout" if isinstance(e, httpx.TimeoutException) else "Connection failed"
                    raise GatewayConnectionError(
                        message="Unable to reach ONDC Gateway",
                        gateway=url,
                        reason=reason_msg,
                        status_code=504 if isinstance(e, httpx.TimeoutException) else 502,
                        error_type=type(e).__name__,
                        error_message=str(e)
                    )
            
            # Use asyncio.sleep instead of time.sleep for async backoff
            await asyncio.sleep(0.5 * attempt)
            
        # If we exit the loop and have a non-2xx response (like a 5xx), raise GatewayConnectionError
        if response and not response.is_success:
            raise GatewayConnectionError(
                message="ONDC Gateway returned an error response after retries",
                gateway=url,
                reason=f"HTTP {response.status_code}",
                status_code=response.status_code,
                response_body=response.text
            )
            
        return response or ONDCResponse(status_code=500, json_data=None, text="Unknown error")


# Global ONDC client instance
ondc_http_client = ONDCHttpClient()


async def safe_ondc_post(
    url: str,
    payload: Dict[str, Any],
    transaction_id: str,
    message_id: str,
    sign: bool = True,
    retries: int = 3,
    subscriber_id: Optional[str] = None,
    unique_key_id: Optional[str] = None,
    private_key_str: Optional[str] = None,
) -> Dict[str, Any]:
    """Wraps ondc_http_client.post with comprehensive error handling to prevent unhandled exceptions and return structured errors."""
    try:
        response = await ondc_http_client.post(
            url,
            payload,
            sign=sign,
            retries=retries,
            subscriber_id=subscriber_id,
            unique_key_id=unique_key_id,
            private_key_str=private_key_str,
        )
        
        try:
            resp_json = response.json() if hasattr(response, 'json') else json.loads(response.text)
            logger.info(f"ONDC Gateway Response for {url}: {json.dumps(resp_json)}")
            ack_status = resp_json.get("message", {}).get("ack", {}).get("status", "ACK")
        except Exception:
            logger.info(f"ONDC Gateway Response for {url}: {response.text}")
            ack_status = "ACK"

        return {
            "transaction_id": transaction_id,
            "message_id": message_id,
            "status": ack_status,
            "raw_response": resp_json if 'resp_json' in locals() else response.text
        }
    except GatewayConnectionError as gce:
        if gce.response_body is not None:
            return {
                "transaction_id": transaction_id,
                "message_id": message_id,
                "status": "GATEWAY_ERROR",
                "gateway_status_code": gce.status_code,
                "gateway_response": gce.response_body
            }
        else:
            return {
                "transaction_id": transaction_id,
                "message_id": message_id,
                "status": "GATEWAY_ERROR",
                "error_type": gce.error_type or "GatewayConnectionError",
                "error_message": gce.error_message or f"{gce.message}: {gce.reason}"
            }
    except Exception as e:
        return {
            "transaction_id": transaction_id,
            "message_id": message_id,
            "status": "GATEWAY_ERROR",
            "error_type": type(e).__name__,
            "error_message": str(e)
        }
