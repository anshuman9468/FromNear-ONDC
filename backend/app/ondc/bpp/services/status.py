import logging
import asyncio
from app.ondc.bpp.client import bpp_client
from app.ondc.bpp.order_builder import build_canonical_order, validate_ret10_payload, _now
from app.ondc.bpp.state_machine import lifecycle_tracker

logger = logging.getLogger(__name__)


class BppStatusService:
    async def process_status(self, payload: dict):
        context = payload.get("context", {})
        message = payload.get("message", {})
        transaction_id = context.get("transaction_id", "default_tx")
        stored_order = lifecycle_tracker.get_stored_order(transaction_id)

        order_id = message.get("order_id") or lifecycle_tracker.get_order_id(transaction_id) or "2026-07-27-1001"
        created_at = lifecycle_tracker.get_created_at(transaction_id) or _now()
        updated_at = _now()

        await asyncio.sleep(0.5)

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
            stored_order=stored_order,
            order_state="Completed" if state_code in ("Order-delivered", "RTO-Delivered") else "In-Progress",
        )

        response_message = {"order": order_obj}
        response_payload = {
            "context": bpp_client._create_response_context(context, "on_status"),
            "message": response_message,
        }

        errors = validate_ret10_payload("on_status", response_payload)
        if errors:
            logger.error(f"RET10 Validation Failed for on_status: {errors}")
            raise ValueError(f"RET10 Schema Error: {errors}")

        lifecycle_tracker.store_order(transaction_id, order_obj, context, created_at, order_id)
        await bpp_client.send_callback(context, "on_status", response_message)
        lifecycle_tracker.record_callback(transaction_id, "on_status", state_code)

    async def handle_status(self, payload: dict):
        await self.process_status(payload)
        logger.info(f"Accepted /status for tx {payload.get('context', {}).get('transaction_id')}")


bpp_status_service = BppStatusService()
