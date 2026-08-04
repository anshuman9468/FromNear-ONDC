import json
import logging
import httpx
import uuid
from datetime import datetime, timezone
from app.ondc.crypto.utils import generate_auth_header
from app.core.settings import settings

logger = logging.getLogger(__name__)


class BppNetworkClient:
    """Client for BPP to send asynchronous callbacks back to BAP or Gateway."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    def _create_response_context(self, request_context: dict, action: str) -> dict:
        """Create context for a DIRECT callback (on_select, on_init, on_confirm, on_update).
        
        ONDC requires the message_id to be the SAME as the incoming request's message_id.
        """
        context = request_context.copy()
        context["action"] = action
        context["bpp_id"] = settings.ONDC_SUBSCRIBER_ID
        context["bpp_uri"] = settings.ONDC_SUBSCRIBER_URI
        context["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        if context.get("city") == "*":
            context["city"] = settings.ONDC_CITY
        # Preserve message_id from the original request — do NOT generate a new one
        return context

    def _create_unsolicited_context(self, base_context: dict, action: str) -> dict:
        """Create context for an UNSOLICITED push (e.g., proactive on_status lifecycle).
        
        These are not direct responses so they need a fresh message_id.
        """
        context = base_context.copy()
        context["action"] = action
        context["bpp_id"] = settings.ONDC_SUBSCRIBER_ID
        context["bpp_uri"] = settings.ONDC_SUBSCRIBER_URI
        context["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        context["message_id"] = str(uuid.uuid4())
        if context.get("city") == "*":
            context["city"] = settings.ONDC_CITY
        return context

    async def send_callback(self, request_context: dict, action: str, message: dict):
        """Send a direct callback — echoes the same message_id as the request."""
        await self._post(request_context, action, message, unsolicited=False)

    async def send_unsolicited(self, base_context: dict, action: str, message: dict):
        """Send an unsolicited push — generates a new message_id."""
        await self._post(base_context, action, message, unsolicited=True)

    async def _post(self, base_context: dict, action: str, message: dict, unsolicited: bool):
        """Internal: build and POST the callback payload."""
        target_uri = base_context.get("bap_uri")
        if not target_uri:
            logger.error("No bap_uri found in context. Cannot send callback.")
            return

        context = self._create_unsolicited_context(base_context, action) if unsolicited \
            else self._create_response_context(base_context, action)

        payload = {"context": context, "message": message}
        body_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        auth_header = generate_auth_header(body_bytes)

        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_header
        }

        url = f"{target_uri.rstrip('/')}/{action}"
        kind = "unsolicited" if unsolicited else "callback"
        
        caller = "internal" if unsolicited else "Workbench/BAP response"
        order_id = message.get("order", {}).get("id", "UNKNOWN")
        
        log_msg = (
            f"\n=== LIFECYCLE TRACE OUTBOUND ===\n"
            f"Timestamp: {context.get('timestamp')}\n"
            f"Action: {action}\n"
            f"Transaction ID: {context.get('transaction_id')}\n"
            f"Message ID: {context.get('message_id')}\n"
            f"Order ID: {order_id}\n"
            f"Request URL: {url}\n"
            f"HTTP Method: POST\n"
            f"Caller: {caller}\n"
        )
        if action == "on_update":
            import traceback
            stack = "".join(traceback.format_stack()[:-1])
            log_msg += f"Stack Frame for on_update:\n{stack}\n"
        
        logger.info(log_msg)

        try:
            response = await self.client.post(url, content=body_bytes, headers=headers)
            response.raise_for_status()
            logger.info(f"=== LIFECYCLE TRACE OUTBOUND SUCCESS ===\nAction: {action}, HTTP Status: {response.status_code}")
        except httpx.HTTPStatusError as e:
            logger.error(f"=== LIFECYCLE TRACE OUTBOUND FAILED ===\nAction: {action}, HTTP Status: {e.response.status_code}, Error: {e.response.text}")
        except Exception as e:
            logger.error(f"=== LIFECYCLE TRACE OUTBOUND FAILED ===\nAction: {action}, Error: {str(e)}")


bpp_client = BppNetworkClient()
