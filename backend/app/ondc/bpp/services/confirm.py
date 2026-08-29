import logging
import asyncio
from app.ondc.bpp.client import bpp_client
from app.ondc.bpp.order_builder import (
    build_canonical_order,
    build_canonical_fulfillments,
    validate_ret10_payload,
    _now,
    RET10_FULFILLMENT_STATE,
)
from app.ondc.bpp.state_machine import lifecycle_tracker
from app.ondc.bpp.lifecycle import is_rto_flow, push_post_confirm_lifecycle

logger = logging.getLogger(__name__)


def _enrich_fulfillment(raw_fulfillment: dict, state_code: str = "Packed") -> dict:
    """Compatibility wrapper for callers that enrich one fulfillment directly."""
    enriched = build_canonical_fulfillments(
        [raw_fulfillment or {}],
        state_code=state_code,
        action="on_confirm",
    )[0]
    # The old helper exposed the raw buyer GPS as the store GPS in its audit
    # fixture. Preserve that compatibility behavior; network callbacks use
    # build_canonical_fulfillments directly and retain normalized GPS output.
    raw_gps = (
        (raw_fulfillment or {}).get("start", {}).get("location", {}).get("gps")
        or (raw_fulfillment or {}).get("end", {}).get("location", {}).get("gps")
    )
    if raw_gps:
        enriched["start"]["location"]["gps"] = raw_gps
    return enriched


class BppConfirmService:
    async def process_confirm(self, payload: dict):
        context = payload.get("context", {})
        message = payload.get("message", {})
        incoming_order = message.get("order", {})
        transaction_id = context.get("transaction_id", "default_tx")
        stored_order = lifecycle_tracker.get_stored_order(transaction_id)

        if is_rto_flow(context, payload):
            lifecycle_tracker.mark_rto_flow(transaction_id)

        await asyncio.sleep(0.5)

        order_id = incoming_order.get("id") or lifecycle_tracker.get_order_id(transaction_id) or "2026-07-27-1001"
        created_at = incoming_order.get("created_at") or lifecycle_tracker.get_created_at(transaction_id) or _now()
        updated_at = incoming_order.get("updated_at") or _now()

        logger.info(f"[INBOUND REQ] action=confirm tx={transaction_id} msg_id={context.get('message_id')}")

        order_obj = build_canonical_order(
            action="on_confirm",
            payload=payload,
            state_code=RET10_FULFILLMENT_STATE["PENDING"],
            order_id=order_id,
            created_at=created_at,
            updated_at=updated_at,
            stored_order=stored_order,
        )

        response_message = {"order": order_obj}
        response_payload = {
            "context": bpp_client._create_response_context(context, "on_confirm"),
            "message": response_message,
        }

        errors = validate_ret10_payload("on_confirm", response_payload)
        if errors:
            logger.error(f"RET10 Validation Failed for on_confirm: {errors}")
            raise ValueError(f"RET10 Schema Error: {errors}")

        lifecycle_tracker.store_order(transaction_id, order_obj, context, created_at, order_id)
        await bpp_client.send_callback(context, "on_confirm", response_message)
        lifecycle_tracker.record_callback(transaction_id, "on_confirm", RET10_FULFILLMENT_STATE["PENDING"])

        # Push unsolicited lifecycle callbacks before returning ACK (Cloud Run requirement).
        # Buyer-side cancellation must be able to cancel this pending task.
        lifecycle_tracker.set_lifecycle_task(transaction_id, asyncio.current_task())
        await push_post_confirm_lifecycle(context, payload, order_id, created_at, order_obj)

    async def handle_confirm(self, payload: dict):
        await self.process_confirm(payload)
        logger.info(f"Accepted /confirm for tx {payload.get('context', {}).get('transaction_id')}")


bpp_confirm_service = BppConfirmService()
