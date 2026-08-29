import json
import logging
import asyncio
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

    @staticmethod
    def _canonicalize_message(request_context: dict, action: str, message: dict) -> dict:
        """Apply the final RET10 completeness guard before signing a callback.

        Individual BPP services build their own response objects, but lifecycle
        callbacks can also be emitted from helper code.  Canonicalizing at this
        single network boundary prevents a partially stored order from ever
        reaching the BAP.
        """
        normalized = dict(message) if isinstance(message, dict) else {}

        if action == "on_search" and isinstance(normalized.get("catalog"), dict):
            # Imported lazily to avoid the search-service/client import cycle.
            from app.ondc.bpp.services.search import _catalog_hours_range, _normalize_catalog_quantities

            normalized["catalog"] = _normalize_catalog_quantities(normalized["catalog"])
            # The core schema defines Time.range as RFC3339 date-times.
            for provider in normalized["catalog"].get("bpp/providers", []):
                for location in provider.get("locations", []):
                    time = location.setdefault("time", {})
                    time["range"] = _catalog_hours_range()
                    if not isinstance(time.get("days"), str) or not time["days"].strip():
                        time["days"] = "1,2,3,4,5,6,7"
            return normalized

        order_actions = {"on_select", "on_init", "on_confirm", "on_status", "on_update", "on_cancel"}
        order = normalized.get("order")
        if action not in order_actions or not isinstance(order, dict):
            return normalized

        from app.ondc.bpp.order_builder import build_canonical_order

        fulfillment = next(
            (
                value for value in order.get("fulfillments", [])
                if isinstance(value, dict)
            ),
            {},
        )
        state_code = (
            fulfillment.get("state", {}).get("descriptor", {}).get("code")
            or ("Serviceable" if action in {"on_select", "on_init"} else "Pending")
        )
        canonical = build_canonical_order(
            action=action,
            payload={"context": request_context, "message": {"order": order}},
            state_code=state_code,
            order_id=order.get("id"),
            created_at=order.get("created_at"),
            updated_at=order.get("updated_at"),
            stored_order=order,
            order_state=order.get("state"),
        )
        # Lifecycle-specific fields are not part of the generic order builder.
        if isinstance(order.get("cancellation"), dict):
            canonical["cancellation"] = order["cancellation"]
        normalized["order"] = canonical
        return normalized

    def _create_response_context(self, request_context: dict, action: str) -> dict:
        """Create context for a DIRECT callback (on_select, on_init, on_confirm, on_update).
        
        ONDC requires the message_id to be the SAME as the incoming request's message_id.
        """
        context = request_context.copy()
        context["domain"] = context.get("domain") or "ONDC:RET10"
        context["country"] = context.get("country") or "IND"
        context["core_version"] = context.get("core_version") or "1.2.0"
        context["bap_id"] = context.get("bap_id") or "buyer-app-mock"
        context["bap_uri"] = context.get("bap_uri") or "http://localhost:3000/mock/bap"
        context["transaction_id"] = context.get("transaction_id") or str(uuid.uuid4())
        context["message_id"] = context.get("message_id") or str(uuid.uuid4())
        context["action"] = action
        # These identify the participant sending the callback. Never echo a
        # malformed target value from an inbound request; Workbench compares
        # them with the BPP registered in the first search response.
        context["bpp_id"] = settings.ONDC_SUBSCRIBER_ID
        context["bpp_uri"] = settings.ONDC_SUBSCRIBER_URI
        context["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        if not context.get("city") or (context.get("city") == "*" and action != "on_search"):
            context["city"] = settings.ONDC_CITY
        # Preserve message_id from the original request — do NOT generate a new one
        return context

    def _create_unsolicited_context(self, base_context: dict, action: str) -> dict:
        """Create context for an UNSOLICITED push (e.g., proactive on_status lifecycle).
        
        These are not direct responses so they need a fresh message_id.
        """
        context = base_context.copy()
        context["domain"] = context.get("domain") or "ONDC:RET10"
        context["country"] = context.get("country") or "IND"
        context["core_version"] = context.get("core_version") or "1.2.0"
        context["bap_id"] = context.get("bap_id") or "buyer-app-mock"
        context["bap_uri"] = context.get("bap_uri") or "http://localhost:3000/mock/bap"
        context["transaction_id"] = context.get("transaction_id") or str(uuid.uuid4())
        context["action"] = action
        context["bpp_id"] = settings.ONDC_SUBSCRIBER_ID
        context["bpp_uri"] = settings.ONDC_SUBSCRIBER_URI
        context["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        context["message_id"] = str(uuid.uuid4())
        if not context.get("city") or (context.get("city") == "*" and action != "on_search"):
            context["city"] = settings.ONDC_CITY
        return context

    async def send_callback(self, request_context: dict, action: str, message: dict):
        """Send a direct callback — echoes the same message_id as the request."""
        await self._post(request_context, action, message, unsolicited=False)
        # Workbench records a direct callback asynchronously.  Yield before a
        # lifecycle task emits the next unsolicited message, otherwise the
        # next step can be classified as out-of-sequence and validated as an
        # empty response even though the callback was accepted by HTTP.
        await asyncio.sleep(1.0)

    async def send_unsolicited(self, base_context: dict, action: str, message: dict):
        """Send an unsolicited push — generates a new message_id."""
        await self._post(base_context, action, message, unsolicited=True)
        # Workbench records unsolicited callbacks asynchronously. Keep
        # callbacks for one transaction ordered before the next lifecycle
        # state is emitted.
        await asyncio.sleep(1.0)

    async def send_callback_error(self, request_context: dict, action: str, error: dict, message: dict | None = None):
        """Send a direct callback with a root ONDC error object."""
        target_uri = request_context.get("bap_uri")
        if not target_uri:
            logger.error("No bap_uri found in context. Cannot send error callback.")
            return

        context = self._create_response_context(request_context, action)
        payload = {"context": context, "error": error}
        if message is not None:
            payload["message"] = self._canonicalize_message(request_context, action, message)

        body_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        auth_header = generate_auth_header(
            body_bytes,
            unique_key_id=settings.ONDC_BPP_UNIQUE_KEY_ID or settings.ONDC_UNIQUE_KEY_ID,
            private_key_str=settings.ONDC_BPP_SIGNING_PRIVATE_KEY or settings.ONDC_SIGNING_PRIVATE_KEY,
        )
        url = f"{target_uri.rstrip('/')}/{action}"
        headers = {"Content-Type": "application/json", "Authorization": auth_header}

        logger.info(
            f"\n=== LIFECYCLE TRACE OUTBOUND ERROR ===\n"
            f"Timestamp: {context.get('timestamp')}\n"
            f"Action: {action}\n"
            f"Transaction ID: {context.get('transaction_id')}\n"
            f"Message ID: {context.get('message_id')}\n"
            f"Request URL: {url}\n"
            f"HTTP Method: POST\n"
            f"Error: {error}\n"
        )

        try:
            response = await self.client.post(url, content=body_bytes, headers=headers)
            response.raise_for_status()
            logger.info(
                "=== LIFECYCLE TRACE OUTBOUND SUCCESS ===\n"
                f"Action: {action}, HTTP Status: {response.status_code}, "
                f"Response: {response.text}"
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"=== LIFECYCLE TRACE OUTBOUND FAILED ===\nAction: {action}, HTTP Status: {e.response.status_code}, Error: {e.response.text}")
        except Exception as e:
            logger.error(f"=== LIFECYCLE TRACE OUTBOUND FAILED ===\nAction: {action}, Error: {str(e)}")

    async def _post(self, base_context: dict, action: str, message: dict, unsolicited: bool):
        """Internal: build and POST the callback payload."""
        target_uri = base_context.get("bap_uri")
        if not target_uri:
            logger.error("No bap_uri found in context. Cannot send callback.")
            return

        context = self._create_unsolicited_context(base_context, action) if unsolicited \
            else self._create_response_context(base_context, action)

        payload = {
            "context": context,
            "message": self._canonicalize_message(base_context, action, message),
        }
        # Revalidate the exact object that is about to be serialized. This
        # catches regressions introduced by the final network canonicalizer.
        if action in {"on_select", "on_init", "on_confirm", "on_status", "on_update", "on_cancel"}:
            from app.ondc.bpp.order_builder import validate_ret10_payload

            wire_errors = validate_ret10_payload(action, payload)
            if wire_errors:
                raise ValueError(f"RET10 wire payload rejected for {action}: {wire_errors}")
        body_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        auth_header = generate_auth_header(
            body_bytes,
            unique_key_id=settings.ONDC_BPP_UNIQUE_KEY_ID or settings.ONDC_UNIQUE_KEY_ID,
            private_key_str=settings.ONDC_BPP_SIGNING_PRIVATE_KEY or settings.ONDC_SIGNING_PRIVATE_KEY,
        )

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
        if action == "on_cancel":
            wire_order = payload["message"].get("order", {})
            wire_fulfillments = wire_order.get("fulfillments", [])
            log_msg += (
                "Wire completeness: "
                f"cancellation_reason={wire_order.get('cancellation', {}).get('reason', {}).get('id')} "
                f"fulfillments={len(wire_fulfillments)} "
                f"start_gps={[f.get('start', {}).get('location', {}).get('gps') for f in wire_fulfillments]} "
                f"start_phones={[f.get('start', {}).get('contact', {}).get('phone') for f in wire_fulfillments]} "
                f"end_phones={[f.get('end', {}).get('contact', {}).get('phone') for f in wire_fulfillments]}\n"
            )
        
        logger.info(log_msg)

        try:
            response = await self.client.post(url, content=body_bytes, headers=headers)
            response.raise_for_status()
            logger.info(
                "=== LIFECYCLE TRACE OUTBOUND SUCCESS ===\n"
                f"Action: {action}, HTTP Status: {response.status_code}, "
                f"Response: {response.text}"
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"=== LIFECYCLE TRACE OUTBOUND FAILED ===\nAction: {action}, HTTP Status: {e.response.status_code}, Error: {e.response.text}")
        except Exception as e:
            logger.error(f"=== LIFECYCLE TRACE OUTBOUND FAILED ===\nAction: {action}, Error: {str(e)}")


bpp_client = BppNetworkClient()
