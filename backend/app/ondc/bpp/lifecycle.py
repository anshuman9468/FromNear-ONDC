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
    if mode in {"prepaid_track", "track", "out_of_stock"}:
        return True
    flow_hint = str(transaction_id or "").lower()
    return (
        "prepaid" in flow_hint
        or "track" in flow_hint
        or (
            transaction_id is not None
            and lifecycle_tracker.is_out_of_stock_flow(transaction_id)
        )
    )


def is_buyer_cancel_flow(context: Dict[str, Any] | None = None) -> bool:
    """Buyer cancellation waits for /cancel instead of pushing delivery status."""
    mode = (settings.ONDC_BPP_FLOW_MODE or "auto").lower()
    if mode in {
        "cancel",
        "buyer_cancel",
        "buyer_cancellation",
    }:
        return True

    flow_hint = str((context or {}).get("transaction_id") or "").lower()
    if is_rto_flow(context or {}):
        return False
    return "buyer_cancel" in flow_hint or "buyer-cancellation" in flow_hint


def is_out_of_stock_flow(transaction_id: str | None = None) -> bool:
    mode = (settings.ONDC_BPP_FLOW_MODE or "auto").lower()
    if mode in {"out_of_stock", "oos"}:
        return True
    flow_hint = str(transaction_id or "").lower()
    return (
        "out_of_stock" in flow_hint
        or "out-of-stock" in flow_hint
        or "oos" in flow_hint
        or (
            transaction_id is not None
            and lifecycle_tracker.is_out_of_stock_flow(transaction_id)
        )
    )


async def _send_lifecycle_callback(
    context: Dict[str, Any],
    action: str,
    order_obj: Dict[str, Any],
    unsolicited: bool,
) -> None:
    # Rebuild at the last boundary so asynchronous callbacks cannot carry a
    # partially stored fulfillment after a lifecycle update or cancellation.
    lifecycle_cancellation = order_obj.get("cancellation")
    fulfillment = next(
        (item for item in order_obj.get("fulfillments", []) if isinstance(item, dict)),
        {},
    )
    callback_state = (
        fulfillment.get("state", {}).get("descriptor", {}).get("code")
        or "Pending"
    )
    order_obj = build_canonical_order(
        action=action,
        payload={"context": context, "message": {"order": order_obj}},
        state_code=callback_state,
        order_id=order_obj.get("id"),
        created_at=order_obj.get("created_at"),
        updated_at=order_obj.get("updated_at"),
        stored_order=order_obj,
        order_state=order_obj.get("state"),
    )
    # The generic order builder intentionally does not own lifecycle-specific
    # fields. Preserve cancellation details across this final rebuild so the
    # RTO on_cancel callback retains cancellation.reason.id on the wire.
    if isinstance(lifecycle_cancellation, dict):
        order_obj["cancellation"] = dict(lifecycle_cancellation)
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

    if is_buyer_cancel_flow(context):
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
    for index, state_code in enumerate(PREPAID_STATUS_SEQUENCE):
        await asyncio.sleep(0.5)
        if lifecycle_tracker.is_cancelled(transaction_id):
            return
        # A normal prepaid flow switches to /track after Picked-up.  Stop the
        # generic delivery loop before it races the direct on_track callback.
        if lifecycle_tracker.is_track_requested(transaction_id) and index >= 3:
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
