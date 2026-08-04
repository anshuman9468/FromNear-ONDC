import logging
import asyncio
from app.ondc.bpp.client import bpp_client
from app.ondc.bpp.order_builder import build_canonical_order, validate_ret10_payload, _now
from app.ondc.bpp.state_machine import lifecycle_tracker

logger = logging.getLogger(__name__)


class BppUpdateService:
    async def process_update(self, payload: dict):
        try:
            context = payload.get("context", {})
            message = payload.get("message", {})
            incoming_order = message.get("order", {})

            await asyncio.sleep(1)

            order_id = incoming_order.get("id", "2026-07-27-1001")
            transaction_id = context.get("transaction_id", "default_tx")
            created_at = incoming_order.get("created_at") or _now()
            updated_at = _now()

            logger.info(f"[INBOUND REQ] action=update tx={transaction_id} msg_id={context.get('message_id')}")

            order_obj = build_canonical_order(
                action="on_update",
                payload=payload,
                state_code="Return-Initiated",
                order_id=order_id,
                created_at=created_at,
                updated_at=updated_at,
            )
            order_obj["state"] = "In-progress"

            response_message = {"order": order_obj}
            response_payload = {
                "context": bpp_client._create_response_context(context, "on_update"),
                "message": response_message
            }

            # Pre-transmission RET10 Validation
            errors = validate_ret10_payload("on_update", response_payload)
            if errors:
                logger.error(f"RET10 Validation Failed for on_update: {errors}")
                raise ValueError(f"RET10 Schema Error: {errors}")

            await bpp_client.send_callback(context, "on_update", response_message)
            lifecycle_tracker.record_callback(transaction_id, "on_update", "Return-Initiated")
            
        except Exception as e:
            logger.exception("Failed to process update")
            raise

    async def handle_update(self, payload: dict):
        asyncio.create_task(self.process_update(payload))
        logger.info(f"Accepted /update for tx {payload.get('context', {}).get('transaction_id')}")


bpp_update_service = BppUpdateService()
