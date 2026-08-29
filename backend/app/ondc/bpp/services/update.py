import logging
import asyncio
from app.ondc.bpp.client import bpp_client
from app.ondc.bpp.order_builder import build_canonical_order, validate_ret10_payload, _now
from app.ondc.bpp.state_machine import lifecycle_tracker
from app.ondc.bpp.lifecycle import is_rto_flow, push_rto_post_update_statuses

logger = logging.getLogger(__name__)


class BppUpdateService:
    async def process_update(self, payload: dict):
        context = payload.get("context", {})
        message = payload.get("message", {})
        incoming_order = message.get("order", {})
        transaction_id = context.get("transaction_id", "default_tx")
        stored_order = lifecycle_tracker.get_stored_order(transaction_id)

        await asyncio.sleep(0.5)

        order_id = incoming_order.get("id") or lifecycle_tracker.get_order_id(transaction_id) or "2026-07-27-1001"
        created_at = incoming_order.get("created_at") or lifecycle_tracker.get_created_at(transaction_id) or _now()
        updated_at = incoming_order.get("updated_at") or _now()

        logger.info(f"[INBOUND REQ] action=update tx={transaction_id} msg_id={context.get('message_id')}")

        if is_rto_flow(context, payload):
            # RTO already emitted the required unsolicited on_update after
            # confirm. The later mock /update advances the RTO state and must
            # not produce a second, out-of-sequence on_update callback.
            order_obj = build_canonical_order(
                action="on_update",
                payload=payload,
                state_code="Return-Initiated",
                order_id=order_id,
                created_at=created_at,
                updated_at=updated_at,
                stored_order=stored_order,
                order_state="In-progress",
            )
            lifecycle_tracker.store_order(transaction_id, order_obj, context, created_at, order_id)
            await push_rto_post_update_statuses(
                context=context,
                payload=payload,
                order_id=order_id,
                created_at=created_at,
                stored_order=order_obj,
            )
            return

        session = lifecycle_tracker.get_or_create(transaction_id)
        session["update_call_count"] += 1
        update_count = session["update_call_count"]

        if update_count == 1:
            state_code = "Return-Initiated"
            order_state = "In-progress"
        else:
            state_code = "Return-Delivered"
            order_state = "Completed"

        order_obj = build_canonical_order(
            action="on_update",
            payload=payload,
            state_code=state_code,
            order_id=order_id,
            created_at=created_at,
            updated_at=updated_at,
            stored_order=stored_order,
            order_state=order_state,
        )

        response_message = {"order": order_obj}
        response_payload = {
            "context": bpp_client._create_response_context(context, "on_update"),
            "message": response_message,
        }

        errors = validate_ret10_payload("on_update", response_payload)
        if errors:
            logger.error(f"RET10 Validation Failed for on_update: {errors}")
            raise ValueError(f"RET10 Schema Error: {errors}")

        lifecycle_tracker.store_order(transaction_id, order_obj, context, created_at, order_id)
        await bpp_client.send_callback(context, "on_update", response_message)
        lifecycle_tracker.record_callback(transaction_id, "on_update", state_code)

        if update_count == 1:
            for followup_state in ("Return-Approved", "Return-Picked"):
                await asyncio.sleep(0.5)
                followup_order = build_canonical_order(
                    action="on_update",
                    payload=payload,
                    state_code=followup_state,
                    order_id=order_id,
                    created_at=created_at,
                    updated_at=_now(),
                    stored_order=order_obj,
                    order_state="In-progress",
                )
                followup_payload = {
                    "context": bpp_client._create_unsolicited_context(context, "on_update"),
                    "message": {"order": followup_order},
                }
                followup_errors = validate_ret10_payload("on_update", followup_payload)
                if followup_errors:
                    logger.error(f"RET10 Validation Failed for unsolicited on_update: {followup_errors}")
                    raise ValueError(f"RET10 Schema Error: {followup_errors}")

                lifecycle_tracker.store_order(transaction_id, followup_order, context, created_at, order_id)
                await bpp_client.send_unsolicited(context, "on_update", {"order": followup_order})
                lifecycle_tracker.record_callback(transaction_id, "on_update", followup_state)
        else:
            # The second update completes the return and is followed by the
            # unsolicited callback represented by the final Workbench step.
            await asyncio.sleep(0.5)
            final_order = build_canonical_order(
                action="on_update",
                payload=payload,
                state_code="Return-Delivered",
                order_id=order_id,
                created_at=created_at,
                updated_at=_now(),
                stored_order=order_obj,
                order_state="Completed",
            )
            final_payload = {
                "context": bpp_client._create_unsolicited_context(context, "on_update"),
                "message": {"order": final_order},
            }
            final_errors = validate_ret10_payload("on_update", final_payload)
            if final_errors:
                logger.error(f"RET10 Validation Failed for final unsolicited on_update: {final_errors}")
                raise ValueError(f"RET10 Schema Error: {final_errors}")
            lifecycle_tracker.store_order(transaction_id, final_order, context, created_at, order_id)
            await bpp_client.send_unsolicited(context, "on_update", {"order": final_order})
            lifecycle_tracker.record_callback(transaction_id, "on_update", "Return-Delivered")

    async def handle_update(self, payload: dict):
        await self.process_update(payload)
        logger.info(f"Accepted /update for tx {payload.get('context', {}).get('transaction_id')}")


bpp_update_service = BppUpdateService()
