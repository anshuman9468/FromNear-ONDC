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
        """Create the context for the response based on the incoming request context."""
        context = request_context.copy()
        context["action"] = action
        context["bpp_id"] = settings.ONDC_SUBSCRIBER_ID
        context["bpp_uri"] = settings.ONDC_SUBSCRIBER_URI
        context["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        context["message_id"] = str(uuid.uuid4())
        return context

    async def send_callback(self, request_context: dict, action: str, message: dict):
        """Send an async callback (e.g., on_search) to the BAP or Gateway."""
        target_uri = request_context.get("bap_uri")
        if not target_uri:
            logger.error("No bap_uri found in context. Cannot send callback.")
            return

        context = self._create_response_context(request_context, action)
        payload = {
            "context": context,
            "message": message
        }

        body_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        auth_header = generate_auth_header(body_bytes)

        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_header
        }

        url = f"{target_uri.rstrip('/')}/{action}"
        logger.info(f"BPP Sending {action} callback to {url}")
        
        try:
            response = await self.client.post(url, content=body_bytes, headers=headers)
            response.raise_for_status()
            logger.info(f"BPP Callback {action} sent successfully. Response: {response.status_code}")
        except httpx.HTTPStatusError as e:
            logger.error(f"BPP Callback {action} failed with status {e.response.status_code}: {e.response.text}")
        except Exception as e:
            logger.error(f"BPP Callback {action} failed to send: {str(e)}")

bpp_client = BppNetworkClient()
