import logging
import asyncio
from app.ondc.bpp.client import bpp_client
from app.ondc.bpp.order_builder import build_canonical_order, validate_ret10_payload, RET10_FULFILLMENT_STATE, _now

logger = logging.getLogger(__name__)


class BppCancelService:
    async def process_cancel(self, payload: dict):
        try:
            context = payload.get("context", {})
            message = payload.get("message", {})
            order_id = message.get("order_id", "2026-07-27-1001")
            cancellation_reason_id = message.get("cancellation_reason_id", "001")

            await asyncio.sleep(1)

            created_at = _now()
            updated_at = _now()

            order_obj = build_canonical_order(
                action="on_cancel",
                payload=payload,
                state_code=RET10_FULFILLMENT_STATE["CANCELLED"],
                order_id=order_id,
                created_at=created_at,
                updated_at=updated_at,
            )
            order_obj["state"] = "Cancelled"
            order_obj["cancellation"] = {
                "cancelled_by": context.get("bap_id", "workbench.ondc.tech"),
                "reason": {
                    "id": cancellation_reason_id
                }
            }

            response_message = {"order": order_obj}
            response_payload = {
                "context": bpp_client._create_response_context(context, "on_cancel"),
                "message": response_message
            }

            # Pre-transmission RET10 Validation
            errors = validate_ret10_payload("on_cancel", response_payload)
            if errors:
                logger.error(f"RET10 Validation Failed for on_cancel: {errors}")
                raise ValueError(f"RET10 Schema Error: {errors}")

            await bpp_client.send_callback(context, "on_cancel", response_message)
        except Exception as e:
            logger.error(f"ERROR in process_cancel: {e}", exc_info=True)

    async def handle_cancel(self, payload: dict):
        asyncio.create_task(self.process_cancel(payload))
        logger.info(f"Accepted /cancel for tx {payload.get('context', {}).get('transaction_id')}")


bpp_cancel_service = BppCancelService()
