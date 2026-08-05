import asyncio
import logging
from typing import Dict, Any, List, Tuple
from app.ondc.bpp.client import bpp_client
from app.ondc.bpp.order_builder import (
    build_canonical_order,
    validate_ret10_payload,
    RET10_FULFILLMENT_STATE,
    _now,
)
from app.ondc.bpp.state_machine import lifecycle_tracker

logger = logging.getLogger(__name__)

PREPAID_STATUS_SEQUENCE = [
    RET10_FULFILLMENT_STATE["PACKED"],
    RET10_FULFILLMENT_STATE["AGENT_ASSIGNED"],
    RET10_FULFILLMENT_STATE["PICKED_UP"],
    RET10_FULFILLMENT_STATE["OUT_FOR_DELIVERY"],
    RET10_FULFILLMENT_STATE["DELIVERED"],
]


async def _send_lifecycle_callback(
    context: Dict[str, Any],
    action: str,
    order_obj: Dict[str, Any],
    unsolicited: bool,
) -> None:
    response_payload = {
        "context": (
            bpp_client._create_unsolicited_context(context, action)
            if unsolicited
            else bpp_client._create_response_context(context, action)
        ),
        "message": {"order": order_obj},
    }
    errors = validate_ret10_payload(action, response_payload)
    if errors:
        raise ValueError(f"RET10 Schema Error for {action}: {errors}")

    if unsolicited:
        await bpp_client.send_unsolicited(context, action, {"order": order_obj})
    else:
        await bpp_client.send_callback(context, action, {"order": order_obj})


async def push_post_confirm_lifecycle(
    context: Dict[str, Any],
    payload: Dict[str, Any],
    order_id: str,
    created_at: str,
    stored_order: Dict[str, Any],
) -> None:
    """Push unsolicited lifecycle callbacks required by Pramaan after on_confirm."""
    transaction_id = context.get("transaction_id", "default_tx")
    item_count = len(stored_order.get("items", []))

    # All flows expect an unsolicited on_status with Pending immediately after confirm.
    pending_order = build_canonical_order(
        action="on_status",
        payload=payload,
        state_code=RET10_FULFILLMENT_STATE["PENDING"],
        order_id=order_id,
        created_at=created_at,
        updated_at=_now(),
        stored_order=stored_order,
    )
    await _send_lifecycle_callback(context, "on_status", pending_order, unsolicited=True)
    lifecycle_tracker.record_callback(transaction_id, "on_status", RET10_FULFILLMENT_STATE["PENDING"])

    await asyncio.sleep(0.5)

    if item_count >= 2:
        # RTO / multi-item flows: unsolicited on_update with Packed fulfillment.
        update_order = build_canonical_order(
            action="on_update",
            payload=payload,
            state_code=RET10_FULFILLMENT_STATE["PACKED"],
            order_id=order_id,
            created_at=created_at,
            updated_at=_now(),
            stored_order=stored_order,
            order_state="In-progress",
        )
        await _send_lifecycle_callback(context, "on_update", update_order, unsolicited=True)
        lifecycle_tracker.record_callback(transaction_id, "on_update", RET10_FULFILLMENT_STATE["PACKED"])
        return

    # Single-item prepaid / return flows: push full delivery status progression.
    for state_code in PREPAID_STATUS_SEQUENCE:
        await asyncio.sleep(0.5)
        status_order = build_canonical_order(
            action="on_status",
            payload=payload,
            state_code=state_code,
            order_id=order_id,
            created_at=created_at,
            updated_at=_now(),
            stored_order=stored_order,
            order_state="Completed" if state_code == RET10_FULFILLMENT_STATE["DELIVERED"] else "In-Progress",
        )
        await _send_lifecycle_callback(context, "on_status", status_order, unsolicited=True)
        lifecycle_tracker.record_callback(transaction_id, "on_status", state_code)
