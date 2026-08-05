import logging
import asyncio
from app.ondc.bpp.client import bpp_client
from app.ondc.bpp.order_builder import build_canonical_order, validate_ret10_payload
from app.ondc.bpp.state_machine import lifecycle_tracker

logger = logging.getLogger(__name__)


class BppInitService:
    async def process_init(self, payload: dict):
        context = payload.get("context", {})
        transaction_id = context.get("transaction_id", "default_tx")
        stored_order = lifecycle_tracker.get_stored_order(transaction_id)

        await asyncio.sleep(0.5)

        order_obj = build_canonical_order(
            action="on_init",
            payload=payload,
            state_code="Serviceable",
            stored_order=stored_order,
        )

        response_message = {"order": order_obj}
        response_payload = {
            "context": bpp_client._create_response_context(context, "on_init"),
            "message": response_message,
        }

        errors = validate_ret10_payload("on_init", response_payload)
        if errors:
            logger.error(f"RET10 Validation Failed for on_init: {errors}")
            raise ValueError(f"RET10 Schema Error: {errors}")

        lifecycle_tracker.store_order(
            transaction_id,
            order_obj,
            context,
            lifecycle_tracker.get_created_at(transaction_id) or context.get("timestamp"),
            lifecycle_tracker.get_order_id(transaction_id) or "pending",
        )
        await bpp_client.send_callback(context, "on_init", response_message)

    async def handle_init(self, payload: dict):
        await self.process_init(payload)
        logger.info(f"Accepted /init for tx {payload.get('context', {}).get('transaction_id')}")


bpp_init_service = BppInitService()
