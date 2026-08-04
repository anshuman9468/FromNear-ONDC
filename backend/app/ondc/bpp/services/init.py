import logging
import asyncio
from app.ondc.bpp.client import bpp_client
from app.ondc.bpp.order_builder import build_canonical_order, validate_ret10_payload

logger = logging.getLogger(__name__)


class BppInitService:
    async def process_init(self, payload: dict):
        try:
            context = payload.get("context", {})

            await asyncio.sleep(1)

            # Build canonical RET10 on_init order
            order_obj = build_canonical_order(
                action="on_init",
                payload=payload,
                state_code="Serviceable"
            )

            response_message = {"order": order_obj}
            response_payload = {
                "context": bpp_client._create_response_context(context, "on_init"),
                "message": response_message
            }

            # Pre-transmission RET10 Validation
            errors = validate_ret10_payload("on_init", response_payload)
            if errors:
                logger.error(f"RET10 Validation Failed for on_init: {errors}")
                raise ValueError(f"RET10 Schema Error: {errors}")

            await bpp_client.send_callback(context, "on_init", response_message)
        except Exception as e:
            logger.error(f"ERROR in process_init: {e}", exc_info=True)

    async def handle_init(self, payload: dict):
        asyncio.create_task(self.process_init(payload))
        logger.info(f"Accepted /init for tx {payload.get('context', {}).get('transaction_id')}")


bpp_init_service = BppInitService()
