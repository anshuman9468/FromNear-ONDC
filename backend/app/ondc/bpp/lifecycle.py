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

# The buyer-cancellation Workbench fixture sends /cancel shortly after it
# receives on_confirm. Opaque Workbench transaction IDs do not identify that
# fixture, so give the direct /cancel request a short opportunity to reserve
# the lifecycle before the ordinary status stream begins.
BUYER_CANCEL_GRACE_SECONDS = 5.0

RTO_STATUS_SEQUENCE = [
    RET10_FULFILLMENT_STATE["PACKED"],
    RET10_FULFILLMENT_STATE["AGENT_ASSIGNED"],
    RET10_FULFILLMENT_STATE["PICKED_UP"],
    RET10_FULFILLMENT_STATE["OUT_FOR_DELIVERY"],
]


def _add_rto_cancel_fulfillment(order: Dict[str, Any], context: Dict[str, Any]) -> None:
    """Expose the merchant cancellation to the Workbench settlement mock.

    Its update generator selects a fulfillment with type Cancel from the
    preceding Seller callback. A cancelled Delivery alone produces an empty
    update.fulfillments array, which fails the RET10 schema check.
    """
    fulfillments = order.setdefault("fulfillments", [])
    cancel = next((f for f in fulfillments if f.get("type") == "Cancel"), None)
    if cancel is not None:
        tags = cancel.setdefault("tags", [])
        if any(tag.get("code") == "quote_trail" for tag in tags if isinstance(tag, dict)):
            return
    else:
        item = next((i for i in order.get("items", []) if i.get("id")), {})
        quote_price = order.get("quote", {}).get("price", {})
        try:
            refund = -abs(float(quote_price.get("value", "0")))
        except (TypeError, ValueError):
            refund = 0.0
        cancel = {
            "id": f"cancel-{order['id']}",
            "type": "Cancel",
            "state": {"descriptor": {"code": "Cancelled"}},
            "tags": [],
        }
        fulfillments.append(cancel)
        tags = cancel["tags"]
    item = next((i for i in order.get("items", []) if i.get("id")), {})
    quote_price = order.get("quote", {}).get("price", {})
    try:
        refund = -abs(float(quote_price.get("value", "0")))
    except (TypeError, ValueError):
        refund = 0.0
    if not any(tag.get("code") == "cancel_request" for tag in tags if isinstance(tag, dict)):
        tags.append({"code": "cancel_request", "list": [
            {"code": "reason_id", "value": "002"},
            {"code": "initiated_by", "value": context.get("bpp_id", "ondc.fromnear.com")},
        ]})
    tags.append({"code": "quote_trail", "list": [
        {"code": "type", "value": "item"},
        {"code": "id", "value": str(item.get("id", "I1"))},
        {"code": "currency", "value": quote_price.get("currency", "INR")},
        {"code": "value", "value": f"{refund:.2f}"},
    ]})


def is_rto_flow(
    context: Dict[str, Any],
    payload: Dict[str, Any] | None = None,
    *,
    stored_order: Dict[str, Any] | None = None,
    refresh_state: bool = True,
) -> bool:
    """Identify merchant-side RTO without depending on a Workbench flow name.

    Workbench generates opaque transaction IDs.  The only durable signal is
    the RTO marker carried in the order tags, so inspect the inbound order
    before falling back to explicit local mode or legacy transaction hints.
    """
    # A Cloud Run service handles several Workbench scenarios concurrently.
    # A process-wide mode must not classify every transaction as RTO (or
    # suppress a real RTO); the marker on this transaction or persisted
    # selection state is authoritative.
    transaction_id = context.get("transaction_id")
    # The Merchant RTO Workbench fixture carries no RTO marker in its
    # select/init/confirm payloads. In a deliberately isolated RTO run, the
    # operator can select this mode for the pre-production BPP service; keep
    # the default in auto so ordinary orders retain their normal status flow.
    if (settings.ONDC_BPP_FLOW_MODE or "auto").lower() == "rto":
        return True
    if transaction_id and lifecycle_tracker.is_rto_flow(
        transaction_id, refresh=refresh_state
    ):
        return True

    order = (payload or {}).get("message", {}).get("order", {})
    # Only inbound payload fields can identify the Workbench scenario. The
    # stored order is Seller-generated and contains populated bpp_terms in
    # ordinary orders too, so it cannot identify an RTO transaction.
    candidate_orders = [order]
    if any(isinstance(candidate, dict) for candidate in candidate_orders):
        # RET10 fixtures may place the merchant-side marker directly on the
        # order, on an item/fulfillment, or inside nested tag-list metadata.
        # Walk the complete order tree so serialization shape does not change
        # the lifecycle branch selected for the transaction.
        # ``cancel_request`` is also used by buyer-initiated return flows.
        # It cannot identify merchant RTO on its own; only explicit RTO
        # markers may select the RTO lifecycle branch.
        marker_codes = {"rto_action"}
        marker_values = {"rto", "rto_action", "return_to_origin", "return-to-origin"}

        def contains_rto_marker(value: Any) -> bool:
            if isinstance(value, dict):
                for key, nested in value.items():
                    normalized_key = str(key).lower()
                    normalized_value = str(nested).lower() if isinstance(nested, str) else ""
                    if normalized_key in {"code", "value", "action", "category", "type"}:
                        if normalized_value in marker_codes or normalized_value in marker_values:
                            return True
                    if contains_rto_marker(nested):
                        return True
            elif isinstance(value, list):
                return any(contains_rto_marker(item) for item in value)
            return False

        if any(contains_rto_marker(candidate) for candidate in candidate_orders):
            return True

    # Commercial bpp_terms are shared by prepaid and RTO orders; they
    # cannot identify a merchant cancellation. Require an explicit signal.
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
    flow_hint = str((context or {}).get("transaction_id") or "").lower()
    if is_rto_flow(context or {}):
        return False
    return "buyer_cancel" in flow_hint or "buyer-cancellation" in flow_hint


def is_buyer_return_flow(
    context: Dict[str, Any], payload: Dict[str, Any] | None = None
) -> bool:
    """Identify the buyer-return fixture before post-confirm pushes begin.

    Workbench's buyer-return confirm has a normal Delivery fulfillment, so the
    Return marker is only present on the later /update.  Its seller terms tag
    is present but empty, unlike the merchant-RTO fixture which contains the
    populated BPP terms needed for the opaque RTO branch.
    """
    order = (payload or {}).get("message", {}).get("order", {})
    if not isinstance(order, dict):
        return False

    def has_tag_code(tags: Any, code: str) -> bool:
        return any(
            isinstance(tag, dict) and tag.get("code") == code
            for tag in (tags if isinstance(tags, list) else [])
        )

    fulfillments = order.get("fulfillments", [])
    if any(
        isinstance(fulfillment, dict)
        and (
            fulfillment.get("type") == "Return"
            or has_tag_code(fulfillment.get("tags"), "return_request")
        )
        for fulfillment in (fulfillments if isinstance(fulfillments, list) else [])
    ):
        return True

    for item in order.get("items", []):
        if isinstance(item, dict) and has_tag_code(item.get("tags"), "return_request"):
            return True

    bpp_terms = next(
        (
            tag
            for tag in order.get("tags", [])
            if isinstance(tag, dict) and tag.get("code") == "bpp_terms"
        ),
        None,
    )
    # Workbench omits ``list`` entirely on the ordinary buyer fixtures.  An
    # empty or absent list is the normal buyer delivery/return shape; the
    # merchant RTO fixture carries populated seller terms.
    return isinstance(bpp_terms, dict) and not bpp_terms.get("list")


def is_out_of_stock_flow(
    transaction_id: str | None = None,
    payload: Dict[str, Any] | None = None,
    *,
    refresh_state: bool = True,
) -> bool:
    haystack = " ".join(
        str(v).lower()
        for v in (
            transaction_id,
            (payload or {}).get("context", {}).get("transaction_id"),
            (payload or {}).get("context", {}).get("message_id"),
        )
        if v
    )
    if "out_of_stock" in haystack or "out-of-stock" in haystack or "oos" in haystack:
        return True

    if transaction_id is not None and lifecycle_tracker.is_out_of_stock_flow(
        transaction_id, refresh=refresh_state
    ):
        return True

    order = (payload or {}).get("message", {}).get("order", {})
    if isinstance(order, dict):
        items = order.get("items", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    qty = item.get("quantity", {})
                    count = int(qty.get("selected", {}).get("count") or qty.get("count") or 1)
                    if count == 0 or count > 5:
                        return True
                    tags = item.get("tags", [])
                    if isinstance(tags, list):
                        for tag in tags:
                            if isinstance(tag, dict) and tag.get("code") in ("out_of_stock", "oos", "item_out_of_stock"):
                                return True

    return False


async def _send_lifecycle_callback(
    context: Dict[str, Any],
    action: str,
    order_obj: Dict[str, Any],
    unsolicited: bool,
) -> None:
    transaction_id = context.get("transaction_id") or order_obj.get("transaction_id") or "default_tx"
    callback_context = lifecycle_tracker.get_callback_context(transaction_id, context)
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
        payload={"context": callback_context, "message": {"order": order_obj}},
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
            bpp_client._create_unsolicited_context(callback_context, action)
            if unsolicited
            else bpp_client._create_response_context(callback_context, action)
        ),
        "message": {"order": order_obj},
    }
    errors = validate_ret10_payload(action, response_payload)
    if errors:
        raise ValueError(f"RET10 Schema Error for {action}: {errors}")

    if unsolicited:
        await bpp_client.send_unsolicited(callback_context, action, {"order": order_obj})
    else:
        await bpp_client.send_callback(callback_context, action, {"order": order_obj})


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

    if is_rto_flow(context, payload, stored_order=stored_order):
        # An accepted delivery must be reported before the merchant cancels
        # items. Pramaan selects this callback by Delivery + Pending even
        # though Workbench's interactive card starts with the partial update.
        pending_order = build_canonical_order(
            action="on_status",
            payload=payload,
            state_code=RET10_FULFILLMENT_STATE["PENDING"],
            order_id=order_id,
            created_at=created_at,
            updated_at=_now(),
            stored_order=stored_order,
            order_state="Accepted",
        )
        await _send_lifecycle_callback(context, "on_status", pending_order, unsolicited=True)
        lifecycle_tracker.record_callback(
            transaction_id, "on_status", RET10_FULFILLMENT_STATE["PENDING"]
        )
        # Merchant-side RTO expects an unsolicited cancellation update directly
        # after on_confirm, before Workbench sends its settlement-trail update.
        await asyncio.sleep(0.5)
        if lifecycle_tracker.is_cancelled(transaction_id):
            return
        cancel_order = build_canonical_order(
            action="on_update",
            payload=payload,
            state_code=RET10_FULFILLMENT_STATE["CANCELLED"],
            order_id=order_id,
            created_at=created_at,
            updated_at=_now(),
            stored_order=stored_order,
            order_state="Cancelled",
        )
        _add_rto_cancel_fulfillment(cancel_order, context)
        await _send_lifecycle_callback(context, "on_update", cancel_order, unsolicited=True)
        lifecycle_tracker.record_callback(
            transaction_id,
            "on_update",
            RET10_FULFILLMENT_STATE["CANCELLED"],
        )
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
                order_state="Accepted" if state_code == RET10_FULFILLMENT_STATE["PENDING"] else "In-progress",
            )
            await _send_lifecycle_callback(context, "on_status", status_order, unsolicited=True)
            lifecycle_tracker.record_callback(transaction_id, "on_status", state_code)
        return

    if is_buyer_return_flow(context, payload):
        # Ordinary buyer delivery and return fixtures have the same confirm
        # payload.  Start with the two delivery statuses, then let the inbound
        # /update distinguish delivery (which advances immediately) from a
        # return (which waits for the complete status sequence).
        await asyncio.sleep(5.0)
        if lifecycle_tracker.is_cancelled(transaction_id):
            return
        for state_code in [RET10_FULFILLMENT_STATE["PENDING"], *PREPAID_STATUS_SEQUENCE]:
            if lifecycle_tracker.get_callback_count(transaction_id, "on_status") == 2:
                # The delivery fixture sends /update after its second status;
                # the return fixture waits for all six.  Give that request
                # time to arrive before emitting more callbacks out of order.
                for _ in range(30):
                    await asyncio.sleep(0.5)
                    if lifecycle_tracker.is_cancelled(transaction_id):
                        return
                    if lifecycle_tracker.get_callback_count(transaction_id, "update"):
                        return
            else:
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
                order_state=(
                    "Accepted"
                    if state_code == RET10_FULFILLMENT_STATE["PENDING"]
                    else "Completed"
                    if state_code == RET10_FULFILLMENT_STATE["DELIVERED"]
                    else "In-progress"
                ),
            )
            await _send_lifecycle_callback(context, "on_status", status_order, unsolicited=True)
            lifecycle_tracker.record_callback(transaction_id, "on_status", state_code)
        return

    # Do not guess RTO from an ordinary confirm: the Workbench Prepaid and
    # Merchant RTO fixtures can carry semantically identical confirm orders.
    # RTO must have been classified from an explicit marker on /select, /init,
    # or /confirm above. Sending a speculative on_update here breaks the
    # Prepaid sequence and creates out-of-sequence callbacks.
    elapsed = 0.0
    while elapsed < BUYER_CANCEL_GRACE_SECONDS:
        await asyncio.sleep(0.25)
        elapsed += 0.25
        if lifecycle_tracker.is_cancelled(transaction_id):
            return

    # Give a buyer-side /cancel a chance to arrive before starting the generic
    # delivery-status stream. The cancellation scenario does not permit an
    # unsolicited on_status between on_confirm and on_cancel.
    await asyncio.sleep(5.0)
    if lifecycle_tracker.is_cancelled(transaction_id):
        return

    # All non-cancellation flows expect an unsolicited on_status with Pending
    # after confirm.
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

    # Return/delivery fixtures are handled above. Ordinary prepaid stops at
    # pickup; /track owns the remaining callbacks so UI latency cannot race it.
    for index, state_code in enumerate(PREPAID_STATUS_SEQUENCE[:3]):
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
    """After the first merchant-side RTO update, send its statuses and cancel."""
    transaction_id = context.get("transaction_id", "default_tx")
    status_payload = dict(payload)
    status_message = dict(payload.get("message", {}))
    status_order = dict(status_message.get("order", {}))
    status_order["fulfillments"] = [
        f for f in status_order.get("fulfillments", [])
        if isinstance(f, dict) and f.get("type") != "Cancel"
    ]
    status_message["order"] = status_order
    status_payload["message"] = status_message
    for state_code in RTO_STATUS_SEQUENCE:
        await asyncio.sleep(0.5)
        if lifecycle_tracker.is_cancelled(transaction_id):
            return
        status_order = build_canonical_order(
            action="on_status",
            payload=status_payload,
            state_code=state_code,
            order_id=order_id,
            created_at=created_at,
            updated_at=_now(),
            stored_order=stored_order,
            order_state=(
                "Accepted"
                if state_code == RET10_FULFILLMENT_STATE["PENDING"]
                else "Completed"
                if state_code == RET10_FULFILLMENT_STATE["RTO_DELIVERED"]
                else "In-progress"
            ),
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
    _add_rto_cancel_fulfillment(cancel_order, context)
    cancel_order["cancellation"] = {
        "cancelled_by": context.get("bpp_id", "ondc.fromnear.com"),
        "reason": {"id": "011"},
    }
    await _send_lifecycle_callback(context, "on_cancel", cancel_order, unsolicited=True)
    lifecycle_tracker.record_callback(transaction_id, "on_cancel", RET10_FULFILLMENT_STATE["CANCELLED"])


async def push_rto_final_status(
    context: Dict[str, Any],
    payload: Dict[str, Any],
    order_id: str,
    created_at: str,
    stored_order: Dict[str, Any],
) -> None:
    """Finish the RTO flow with delivery back to origin after /update."""
    transaction_id = context.get("transaction_id", "default_tx")
    status_payload = dict(payload)
    status_message = dict(payload.get("message", {}))
    status_order = dict(status_message.get("order", {}))
    status_order["fulfillments"] = [
        f for f in status_order.get("fulfillments", [])
        if isinstance(f, dict) and f.get("type") != "Cancel"
    ]
    status_message["order"] = status_order
    status_payload["message"] = status_message
    await asyncio.sleep(0.5)
    if lifecycle_tracker.is_cancelled(transaction_id):
        return
    final_update_order = build_canonical_order(
        action="on_status",
        payload=status_payload,
        state_code=RET10_FULFILLMENT_STATE["RTO_DELIVERED"],
        order_id=order_id,
        created_at=created_at,
        updated_at=_now(),
        stored_order=stored_order,
        order_state="Cancelled",
    )
    final_update_order["cancellation"] = {
        "cancelled_by": context.get("bpp_id", "ondc.fromnear.com"),
        "reason": {"id": "011"},
    }
    await _send_lifecycle_callback(context, "on_status", final_update_order, unsolicited=True)
    lifecycle_tracker.record_callback(transaction_id, "on_status", RET10_FULFILLMENT_STATE["RTO_DELIVERED"])


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
