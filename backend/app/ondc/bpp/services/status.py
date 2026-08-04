import logging
import asyncio
from app.ondc.bpp.client import bpp_client
from app.ondc.bpp.order_builder import build_canonical_order, validate_ret10_payload, _now
from app.ondc.bpp.state_machine import lifecycle_tracker

logger = logging.getLogger(__name__)


class BppStatusService:
    async def process_status(self, payload: dict):
        try:
            context = payload.get("context", {})
            message = payload.get("message", {})
            order_id = message.get("order_id", "2026-07-27-1001")
            transaction_id = context.get("transaction_id", "default_tx")

            await asyncio.sleep(1)

            created_at = _now()
            updated_at = _now()

            requested_state = message.get("state_code")
            state_code = lifecycle_tracker.advance_status_state(transaction_id, requested_state)

            logger.info(f"[INBOUND REQ] action=status tx={transaction_id} msg_id={context.get('message_id')} state_code={state_code}")

            order_obj = build_canonical_order(
                action="on_status",
                payload=payload,
                state_code=state_code,
                order_id=order_id,
                created_at=created_at,
                updated_at=updated_at,
            )

            response_message = {"order": order_obj}
            response_payload = {
                "context": bpp_client._create_response_context(context, "on_status"),
                "message": response_message
            }

            # Pre-transmission RET10 Validation
            errors = validate_ret10_payload("on_status", response_payload)
            if errors:
                logger.error(f"RET10 Validation Failed for on_status: {errors}")
                raise ValueError(f"RET10 Schema Error: {errors}")

            await bpp_client.send_callback(context, "on_status", response_message)
            lifecycle_tracker.record_callback(transaction_id, "on_status", state_code)
        except Exception as e:
            logger.error(f"ERROR in process_status: {e}", exc_info=True)

    async def handle_status(self, payload: dict):
        asyncio.create_task(self.process_status(payload))
        logger.info(f"Accepted /status for tx {payload.get('context', {}).get('transaction_id')}")


bpp_status_service = BppStatusService()
