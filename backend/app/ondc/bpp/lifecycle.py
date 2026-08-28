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
from app.core.settings import settings

logger = logging.getLogger(__name__)

PREPAID_STATUS_SEQUENCE = [
    RET10_FULFILLMENT_STATE["PACKED"],
    RET10_FULFILLMENT_STATE["AGENT_ASSIGNED"],
    RET10_FULFILLMENT_STATE["PICKED_UP"],
    RET10_FULFILLMENT_STATE["OUT_FOR_DELIVERY"],
    RET10_FULFILLMENT_STATE["DELIVERED"],
]
PREPAID_PRE_TRACK_STATUS_SEQUENCE = [
    RET10_FULFILLMENT_STATE["PENDING"],
    RET10_FULFILLMENT_STATE["PACKED"],
    RET10_FULFILLMENT_STATE["AGENT_ASSIGNED"],
    RET10_FULFILLMENT_STATE["PICKED_UP"],
]
PREPAID_POST_TRACK_STATUS_SEQUENCE = [
    RET10_FULFILLMENT_STATE["OUT_FOR_DELIVERY"],
    RET10_FULFILLMENT_STATE["DELIVERED"],
]

RTO_STATUS_SEQUENCE = [
    RET10_FULFILLMENT_STATE["RTO_INITIATED"],
    RET10_FULFILLMENT_STATE["RTO_DISPOSED"],
    RET10_FULFILLMENT_STATE["RTO_DELIVERED"],
    RET10_FULFILLMENT_STATE["CANCELLED"],
]


def is_rto_flow(context: Dict[str, Any], payload: Dict[str, Any] | None = None) -> bool:
    """Workbench does not send a formal flow name, so use the pasted tx/message hint."""
    flow_mode = (settings.ONDC_BPP_FLOW_MODE or "auto").lower()
    if flow_mode == "rto":
        return True
    if flow_mode in {"buyer_return", "return", "status"}:
        return False

    haystack = " ".join(
        str(value).lower()
        for value in (
            context.get("transaction_id"),
            context.get("message_id"),
            (payload or {}).get("context", {}).get("transaction_id"),
            (payload or {}).get("context", {}).get("message_id"),
        )
        if value
    )
    return "rto" in haystack or "merchant" in haystack


def is_prepaid_track_flow(transaction_id: str | None = None) -> bool:
    mode = (settings.ONDC_BPP_FLOW_MODE or "auto").lower()
    return mode in {"prepaid_track", "track", "out_of_stock"} or (
        transaction_id is not None and lifecycle_tracker.is_out_of_stock_flow(transaction_id)
    )


def is_buyer_cancel_flow() -> bool:
    """Buyer cancellation waits for /cancel instead of pushing delivery status."""
    return (settings.ONDC_BPP_FLOW_MODE or "auto").lower() in {
        "cancel",
        "buyer_cancel",
        "buyer_cancellation",
    }


def is_out_of_stock_flow(transaction_id: str | None = None) -> bool:
    return (settings.ONDC_BPP_FLOW_MODE or "auto").lower() in {"out_of_stock", "oos"} or (
        transaction_id is not None and lifecycle_tracker.is_out_of_stock_flow(transaction_id)
    )


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

    if is_buyer_cancel_flow():
        return

    if is_rto_flow(context, payload):
        if lifecycle_tracker.is_cancelled(transaction_id):
            return
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

    if is_prepaid_track_flow(transaction_id):
        for state_code in PREPAID_PRE_TRACK_STATUS_SEQUENCE:
            await asyncio.sleep(0.5)
            if lifecycle_tracker.is_cancelled(transaction_id):
                return
            status_order = build_canonical_order(
                action="on_status",
                payload=payload,
                state_code=state_code,
                order_id=order_id,
                created_at=created_at,
                updated_at=_now(),
                stored_order=stored_order,
                order_state="In-progress",
            )
            await _send_lifecycle_callback(context, "on_status", status_order, unsolicited=True)
            lifecycle_tracker.record_callback(transaction_id, "on_status", state_code)
        return

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

    # Let buyer-side cancel arrive before delivery-status pushes begin.
    await asyncio.sleep(2.0)

    # Workbench return flows expect the full delivery status progression before update.
    for state_code in PREPAID_STATUS_SEQUENCE:
        await asyncio.sleep(0.5)
        if lifecycle_tracker.is_cancelled(transaction_id):
            return
        status_order = build_canonical_order(
            action="on_status",
            payload=payload,
            state_code=state_code,
            order_id=order_id,
            created_at=created_at,
            updated_at=_now(),
            stored_order=stored_order,
            order_state="Completed" if state_code == RET10_FULFILLMENT_STATE["DELIVERED"] else "In-progress",
        )
        await _send_lifecycle_callback(context, "on_status", status_order, unsolicited=True)
        lifecycle_tracker.record_callback(transaction_id, "on_status", state_code)


async def push_rto_post_update_statuses(
    context: Dict[str, Any],
    payload: Dict[str, Any],
    order_id: str,
    created_at: str,
    stored_order: Dict[str, Any],
) -> None:
    """After merchant-side RTO update, Workbench expects unsolicited on_status callbacks."""
    transaction_id = context.get("transaction_id", "default_tx")
    for state_code in RTO_STATUS_SEQUENCE:
        await asyncio.sleep(0.5)
        if lifecycle_tracker.is_cancelled(transaction_id):
            return
        status_order = build_canonical_order(
            action="on_status",
            payload=payload,
            state_code=state_code,
            order_id=order_id,
            created_at=created_at,
            updated_at=_now(),
            stored_order=stored_order,
            order_state="Completed" if state_code == RET10_FULFILLMENT_STATE["RTO_DELIVERED"] else "In-progress",
        )
        await _send_lifecycle_callback(context, "on_status", status_order, unsolicited=True)
        lifecycle_tracker.record_callback(transaction_id, "on_status", state_code)

    await asyncio.sleep(0.5)
    cancel_order = build_canonical_order(
        action="on_cancel",
        payload=payload,
        state_code=RET10_FULFILLMENT_STATE["CANCELLED"],
        order_id=order_id,
        created_at=created_at,
        updated_at=_now(),
        stored_order=stored_order,
        order_state="Cancelled",
    )
    cancel_order["cancellation"] = {
        "cancelled_by": context.get("bpp_id", "ondc.fromnear.com"),
        "reason": {"id": "011"},
    }
    await _send_lifecycle_callback(context, "on_cancel", cancel_order, unsolicited=True)
    lifecycle_tracker.record_callback(transaction_id, "on_cancel", RET10_FULFILLMENT_STATE["CANCELLED"])

    await asyncio.sleep(0.5)
    final_status_order = build_canonical_order(
        action="on_status",
        payload=payload,
        state_code=RET10_FULFILLMENT_STATE["CANCELLED"],
        order_id=order_id,
        created_at=created_at,
        updated_at=_now(),
        stored_order=cancel_order,
        order_state="Cancelled",
    )
    await _send_lifecycle_callback(context, "on_status", final_status_order, unsolicited=True)
    lifecycle_tracker.record_callback(transaction_id, "on_status", "Final-Cancelled")


async def push_prepaid_post_track_statuses(
    context: Dict[str, Any],
    payload: Dict[str, Any],
    order_id: str,
    created_at: str,
    stored_order: Dict[str, Any],
) -> None:
    """After /track, prepaid tracking flow expects the final delivery statuses."""
    transaction_id = context.get("transaction_id", "default_tx")
    for state_code in PREPAID_POST_TRACK_STATUS_SEQUENCE:
        await asyncio.sleep(0.5)
        if lifecycle_tracker.is_cancelled(transaction_id):
            return
        status_order = build_canonical_order(
            action="on_status",
            payload=payload,
            state_code=state_code,
            order_id=order_id,
            created_at=created_at,
            updated_at=_now(),
            stored_order=stored_order,
            order_state="Completed" if state_code == RET10_FULFILLMENT_STATE["DELIVERED"] else "In-progress",
        )
        await _send_lifecycle_callback(context, "on_status", status_order, unsolicited=True)
        lifecycle_tracker.record_callback(transaction_id, "on_status", state_code)
