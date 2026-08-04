import logging
import asyncio
from app.ondc.bpp.client import bpp_client
from app.ondc.bpp.order_builder import build_canonical_order, validate_ret10_payload

logger = logging.getLogger(__name__)


class BppSelectService:
    async def process_select(self, payload: dict):
        try:
            context = payload.get("context", {})

            await asyncio.sleep(1)

            # Build canonical RET10 on_select order
            order_obj = build_canonical_order(
                action="on_select",
                payload=payload,
                state_code="Serviceable"
            )

            response_message = {"order": order_obj}
            response_payload = {
                "context": bpp_client._create_response_context(context, "on_select"),
                "message": response_message
            }

            # Pre-transmission RET10 Validation
            errors = validate_ret10_payload("on_select", response_payload)
            if errors:
                logger.error(f"RET10 Validation Failed for on_select: {errors}")
                raise ValueError(f"RET10 Schema Error: {errors}")

            await bpp_client.send_callback(context, "on_select", response_message)
        except Exception as e:
            logger.error(f"ERROR in process_select: {e}", exc_info=True)

    async def handle_select(self, payload: dict):
        asyncio.create_task(self.process_select(payload))
        logger.info(f"Accepted /select for tx {payload.get('context', {}).get('transaction_id')}")


bpp_select_service = BppSelectService()
