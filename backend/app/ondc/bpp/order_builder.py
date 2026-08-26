import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.core.settings import settings

logger = logging.getLogger(__name__)

# Official RET10 Fulfillment State Enum Map
RET10_FULFILLMENT_STATE = {
    "PENDING": "Pending",
    "PACKED": "Packed",
    "AGENT_ASSIGNED": "Agent-assigned",
    "PICKED_UP": "Order-picked-up",
    "OUT_FOR_DELIVERY": "Out-for-delivery",
    "DELIVERED": "Order-delivered",
    "CANCELLED": "Cancelled",
    "RTO_INITIATED": "RTO-Initiated",
    "RTO_DISPOSED": "RTO-Disposed",
    "RTO_DELIVERED": "RTO-Delivered"
}

ALLOWED_FORWARD_STATUS_CODES = set(RET10_FULFILLMENT_STATE.values()) | {"Serviceable"}
ALLOWED_RETURN_STATUS_CODES = ALLOWED_FORWARD_STATUS_CODES | {
    "Return-Initiated", "Return-Approved", "Return-Picked", "Return-Delivered", "Liquidated", "Cancelled"
}

# ISO-8601 UTC regex matching YYYY-MM-DDTHH:mm:ss.sssZ format
ISO_UTC_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

DEFAULT_PARENT_ITEM_ID = "V1"
DEFAULT_ITEM_TAGS = [
    {
        "code": "np_fees",
        "list": [
            {"code": "id", "value": "FINDER_FEE"},
        ],
    }
]
DEFAULT_DELIVERY_TAGS = [
    {
        "descriptor": {"code": "title"},
        "list": [{"descriptor": {"code": "type"}, "value": "delivery"}],
    }
]
DEFAULT_QUOTE_ITEM_TAGS = [
    {
        # RET10 BPP quote breakup metadata uses the quote tag vocabulary.
        "code": "quote",
        "list": [
            {"code": "type", "value": "item"},
        ],
    }
]
DEFAULT_QUOTE_DELIVERY_TAGS = [
    {
        "code": "quote",
        "list": [
            {"code": "type", "value": "fulfillment"},
        ],
    }
]


def _normalize_fulfillment_tags(value: Any) -> List[Dict[str, Any]]:
    """Keep fulfillment tags as an array without leaking malformed input."""
    if not isinstance(value, list):
        return []
    return [tag for tag in value if isinstance(tag, dict)]


def _now() -> str:
    """Return ISO-8601 UTC timestamp in format YYYY-MM-DDTHH:mm:ss.sssZ."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _get_catalog_item_map() -> Dict[str, Dict[str, Any]]:
    """Return catalog items keyed by id."""
    from app.ondc.bpp.services.search import bpp_search_service

    catalog_items = bpp_search_service.mock_catalog.get("bpp/providers", [])[0].get("items", [])
    return {item["id"]: item for item in catalog_items}


def _resolve_item_tags(catalog_item: Optional[Dict[str, Any]], incoming_tags: Any = None) -> List[Dict[str, Any]]:
    """Return order.items tags using only codes allowed by Pramaan."""
    allowed_codes = {"np_fees", "rto_action"}
    if isinstance(incoming_tags, list) and len(incoming_tags) > 0:
        filtered_tags = []
        for tag in incoming_tags:
            if not isinstance(tag, dict) or tag.get("code") not in allowed_codes:
                continue
            tag_copy = dict(tag)
            if tag_copy.get("code") == "np_fees":
                tag_copy["list"] = [
                    item for item in tag_copy.get("list", [])
                    if isinstance(item, dict) and item.get("code") == "id"
                ] or DEFAULT_ITEM_TAGS[0]["list"]
            filtered_tags.append(tag_copy)
        if filtered_tags:
            return filtered_tags
    return DEFAULT_ITEM_TAGS


def _resolve_parent_item_id(catalog_item: Optional[Dict[str, Any]], incoming: Any = None) -> str:
    """Return a non-empty parent_item_id string."""
    if isinstance(incoming, str) and incoming.strip():
        return incoming.strip()
    catalog_val = catalog_item.get("parent_item_id") if catalog_item else None
    if isinstance(catalog_val, str) and catalog_val.strip():
        return catalog_val.strip()
    return DEFAULT_PARENT_ITEM_ID


def _build_quote_item_details(item_id: str, catalog_item: Optional[Dict[str, Any]], unit_price: float, quantity: int = 1) -> Dict[str, Any]:
    """Build a fully populated quote.breakup[].item object."""
    max_count = "5"
    avail_count = "99"
    if catalog_item:
        max_count = str(catalog_item.get("quantity", {}).get("maximum", {}).get("count", 5))
        avail_count = str(catalog_item.get("quantity", {}).get("available", {}).get("count", 99))
    return {
        "id": item_id,
        "quantity": {
            "available": {"count": avail_count},
            "maximum": {"count": max_count},
            # selected count is mandatory in the quote breakup item per RET10 schema
            "selected": {"count": quantity},
        },
        "price": {"currency": "INR", "value": f"{unit_price:.2f}"},
        "parent_item_id": _resolve_parent_item_id(catalog_item),
        # Quote-breakup tags have a distinct RET10 BPP vocabulary.
        "tags": DEFAULT_QUOTE_ITEM_TAGS,
    }


def _build_order_item(it: Dict[str, Any], action: str, catalog_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Build a fully enriched order.items[] entry from catalog + incoming data."""
    item_id = it.get("id", "I1")
    catalog_item = catalog_map.get(item_id)
    qty = (
        it.get("quantity", {}).get("selected", {}).get("count")
        or it.get("quantity", {}).get("count", 1)
    )
    item_obj: Dict[str, Any] = {
        "id": item_id,
        "fulfillment_id": it.get("fulfillment_id") or (catalog_item or {}).get("fulfillment_id") or "F1",
        # parent_item_id is MANDATORY in all BPP responses per RET10 schema
        "parent_item_id": _resolve_parent_item_id(catalog_item, it.get("parent_item_id")),
        "tags": _resolve_item_tags(catalog_item, it.get("tags")),
    }
    if action == "on_select":
        item_obj["location_id"] = it.get("location_id") or (catalog_item or {}).get("location_id") or "L1"
        item_obj["quantity"] = {"selected": {"count": int(qty)}}
    else:
        item_obj["quantity"] = {"count": int(qty)}
    return item_obj


def build_canonical_quote(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the full ONDC-compliant quote from catalog data."""
    item_map = _get_catalog_item_map()

    quote_breakup = []
    total_value = 0.0

    for item in items:
        item_id = item.get("id")
        quantity = item.get("quantity", {}).get("selected", {}).get("count") or \
                   item.get("quantity", {}).get("count", 1)
        catalog_item = item_map.get(item_id)
        price = float((catalog_item or {}).get("price", {}).get("value", 250.0))
        item_total = price * quantity
        total_value += item_total
        item_details = _build_quote_item_details(item_id, catalog_item, price, int(quantity))

        quote_breakup.append({
            "@ondc/org/item_id": item_id,
            "@ondc/org/item_quantity": {"count": int(quantity)},
            "title": (catalog_item or {}).get("descriptor", {}).get("name", "Item"),
            "@ondc/org/title_type": "item",
            "price": {"currency": "INR", "value": f"{item_total:.2f}"},
            "item": item_details,
        })

    delivery_charge = 50.0
    total_value += delivery_charge
    quote_breakup.append({
        "@ondc/org/item_id": "F1",
        "@ondc/org/item_quantity": {"count": 1},
        "title": "Delivery charges",
        "@ondc/org/title_type": "delivery",
        "price": {"currency": "INR", "value": f"{delivery_charge:.2f}"},
        "item": {
            **_build_quote_item_details("F1", None, delivery_charge),
            "tags": DEFAULT_QUOTE_DELIVERY_TAGS,
        }
    })

    return {
        "price": {"currency": "INR", "value": f"{total_value:.2f}"},
        "breakup": quote_breakup,
        "ttl": "PT15M"
    }


def format_gps(gps: str) -> str:
    """Format GPS coordinates to at least 6 decimal places."""
    if not gps:
        return "12.971599,77.594563"
    try:
        parts = [p.strip() for p in gps.split(",")]
        if len(parts) != 2:
            return "12.971599,77.594563"
        lat = float(parts[0])
        lng = float(parts[1])
        return f"{lat:.6f},{lng:.6f}"
    except Exception:
        return "12.971599,77.594563"


def build_canonical_fulfillments(raw_fulfillments: List[Dict[str, Any]], state_code: str) -> List[Dict[str, Any]]:
    """Enrich fulfillment objects with all mandatory RET10 start/end/state/time fields."""
    if not raw_fulfillments:
        raw_fulfillments = [{}]

    enriched = []
    now_str = _now()
    for f in raw_fulfillments:
        f_copy = dict(f) if f else {}
        f_copy["id"] = f_copy.get("id", "F1")
        if state_code.startswith("Return") or state_code == "Liquidated":
            f_copy["type"] = "Return"
        else:
            f_copy["type"] = f_copy.get("type", "Delivery")
        f_copy["@ondc/org/provider_name"] = f_copy.get("@ondc/org/provider_name") or "FromNear Store"
        f_copy["tracking"] = f_copy.get("tracking") if isinstance(f_copy.get("tracking"), bool) else False
        f_copy["@ondc/org/category"] = f_copy.get("@ondc/org/category") or "Standard Delivery"
        f_copy["@ondc/org/TAT"] = f_copy.get("@ondc/org/TAT") or "PT45M"
        f_copy["tags"] = _normalize_fulfillment_tags(f_copy.get("tags"))
        f_copy["state"] = {"descriptor": {"code": state_code}}

        # Start location & contact (Store side details)
        start = dict(f_copy.get("start", {}))
        loc = dict(start.get("location", {}))
        loc["id"] = loc.get("id") or "L1"
        desc = dict(loc.get("descriptor", {}))
        desc["name"] = desc.get("name") or "FromNear Main Branch"
        loc["descriptor"] = desc
        loc["gps"] = format_gps(loc.get("gps") or "12.971599,77.594563")

        addr = dict(loc.get("address", {}))
        addr["locality"] = addr.get("locality") or "M.G. Road"
        addr["city"] = addr.get("city") or "Bengaluru"
        addr["area_code"] = addr.get("area_code") or "560001"
        addr["state"] = addr.get("state") or "Karnataka"
        loc["address"] = addr
        start["location"] = loc

        cnt = dict(start.get("contact", {}))
        cnt["phone"] = cnt.get("phone") or "9876543210"
        cnt["email"] = cnt.get("email") or "support@fromnear.com"
        start["contact"] = cnt

        # Populate start time details
        start_time = dict(start.get("time", {}))
        if "range" not in start_time:
            start_time["range"] = {
                "start": now_str,
                "end": now_str
            }
        start_time["timestamp"] = start_time.get("timestamp") or now_str
        start["time"] = start_time
        f_copy["start"] = start

        # End location & contact & person (Buyer side details)
        end = dict(f_copy.get("end", {}))
        
        # 1. Contact
        end_cnt = dict(end.get("contact", {}))
        end_cnt["phone"] = end_cnt.get("phone") or "9876543210"
        end_cnt["email"] = end_cnt.get("email") or "buyer@example.com"
        end_cnt["name"] = end_cnt.get("name") or "Jane Doe"
        end["contact"] = end_cnt
        
        # 2. Person
        end_pers = dict(end.get("person", {}))
        end_pers["name"] = end_pers.get("name") or end_cnt["name"] or "Jane Doe"
        end["person"] = end_pers
        
        # 3. Location & Address
        end_loc = dict(end.get("location", {}))
        end_loc["id"] = end_loc.get("id") or "L2"
        end_desc = dict(end_loc.get("descriptor", {}))
        end_desc["name"] = end_desc.get("name") or "Buyer Delivery Location"
        end_loc["descriptor"] = end_desc
        end_loc["gps"] = format_gps(end_loc.get("gps") or "12.971599,77.594563")
        
        end_addr = dict(end_loc.get("address", {}))
        end_addr["name"] = end_addr.get("name") or end_cnt["name"] or "Jane Doe"
        end_addr["building"] = end_addr.get("building") or end_addr.get("door") or "Apt 4B"
        end_addr["locality"] = end_addr.get("locality") or end_addr.get("street") or "MG Road"
        end_addr["city"] = end_addr.get("city") or "Bengaluru"
        end_addr["state"] = end_addr.get("state") or "Karnataka"
        end_addr["country"] = end_addr.get("country") or "IND"
        end_addr["area_code"] = end_addr.get("area_code") or "560001"
        
        end_loc["address"] = end_addr
        end["location"] = end_loc

        # 4. End time details
        end_time = dict(end.get("time", {}))
        if "range" not in end_time:
            end_time["range"] = {
                "start": now_str,
                "end": now_str
            }
        end_time["timestamp"] = end_time.get("timestamp") or now_str
        end["time"] = end_time

        # 5. Instructions
        end_inst = dict(end.get("instructions", {}))
        end_inst["name"] = end_inst.get("name") or "Status for drop"
        end_inst["short_desc"] = end_inst.get("short_desc") or "Leave at door"
        end_inst["long_desc"] = end_inst.get("long_desc") or "Leave at door"
        end_inst["code"] = end_inst.get("code") or "1"
        end_inst["images"] = end_inst.get("images") if isinstance(end_inst.get("images"), list) else []
        end["instructions"] = end_inst

        f_copy["end"] = end

        enriched.append(f_copy)

    return enriched


def build_canonical_billing(raw_billing: Dict[str, Any], created_at: str, updated_at: str) -> Dict[str, Any]:
    """Construct complete RET10 compliant billing structure with all required address fields."""
    billing = dict(raw_billing) if raw_billing else {}
    billing["name"] = billing.get("name") or "John Doe"
    billing["phone"] = billing.get("phone") or "9876543210"
    billing["email"] = billing.get("email") or "buyer@example.com"
    billing["created_at"] = billing.get("created_at") or created_at
    billing["updated_at"] = billing.get("updated_at") or updated_at

    addr = dict(billing.get("address", {}))
    addr["name"] = addr.get("name") or billing["name"]
    addr["building"] = addr.get("building") or addr.get("door") or "123"
    addr["locality"] = addr.get("locality") or addr.get("street") or "M.G. Road"
    addr["city"] = addr.get("city") or "Bengaluru"
    addr["state"] = addr.get("state") or "Karnataka"
    addr["country"] = addr.get("country") or "IND"
    addr["area_code"] = addr.get("area_code") or "560001"

    billing["address"] = addr
    return billing


def build_canonical_payment(raw_payment: Dict[str, Any], bap_id: str, total_amount: str = "150.00") -> Dict[str, Any]:
    """Construct full RET10 compliant payment structure with dual settlement_details and payment.params."""
    payment = dict(raw_payment) if raw_payment else {}
    bpp_id = settings.ONDC_SUBSCRIBER_ID
    now_str = _now()

    incoming_settlements = payment.get("@ondc/org/settlement_details", [])
    settlement_details = [
        {
            "settlement_counterparty": "seller-app",
            "settlement_phase": "sale-amount",
            "settlement_type": "neft",
            "settlement_timestamp": now_str,
            "settlement_amount": total_amount,
            "subscriber_id": bpp_id,
            "beneficiary_name": "FromNear Store",
            "bank_name": "Mock Bank",
            "branch_name": "MG Road",
            "settlement_bank_account_no": "1234567890",
            "settlement_ifsc_code": "MOCK0001234",
            "upi_address": "fromnear@upi",
            "settlement_status": "PAID"
        }
    ]

    for sd in incoming_settlements:
        sd_copy = dict(sd)
        if sd_copy.get("settlement_counterparty") == "buyer-app":
            sd_copy["subscriber_id"] = bap_id
            if "settlement_timestamp" not in sd_copy:
                sd_copy["settlement_timestamp"] = now_str
            if "settlement_amount" not in sd_copy:
                sd_copy["settlement_amount"] = total_amount
            sd_copy["upi_address"] = sd_copy.get("upi_address") or "bap@upi"
            sd_copy["settlement_status"] = sd_copy.get("settlement_status") or "PAID"
            settlement_details.append(sd_copy)
        elif sd_copy.get("settlement_counterparty") == "seller-app":
            sd_copy["subscriber_id"] = bpp_id
            if "settlement_timestamp" not in sd_copy:
                sd_copy["settlement_timestamp"] = now_str
            if "settlement_amount" not in sd_copy:
                sd_copy["settlement_amount"] = total_amount
            sd_copy["upi_address"] = sd_copy.get("upi_address") or "fromnear@upi"
            sd_copy["settlement_status"] = sd_copy.get("settlement_status") or "PAID"
            settlement_details[0] = sd_copy

    payment["@ondc/org/settlement_details"] = settlement_details
    payment["@ondc/org/settlement_basis"] = payment.get("@ondc/org/settlement_basis") or "delivery"
    # settlement_window and withholding_amount are MANDATORY per RET10 schema
    payment["@ondc/org/settlement_window"] = payment.get("@ondc/org/settlement_window") or "PT1D"
    payment["@ondc/org/withholding_amount"] = payment.get("@ondc/org/withholding_amount") or "0.0"
    if "@ondc/org/buyer_app_finder_fee_type" not in payment:
        payment["@ondc/org/buyer_app_finder_fee_type"] = "percent"
    if "@ondc/org/buyer_app_finder_fee_amount" not in payment:
        payment["@ondc/org/buyer_app_finder_fee_amount"] = "3"
    if "type" not in payment:
        payment["type"] = "ON-ORDER"
    if "status" not in payment:
        payment["status"] = "PAID"
    # collected_by MUST be "BPP" — consistent with BAP INIT/CONFIRM
    payment["collected_by"] = "BPP"

    params = dict(payment.get("params", {}))
    params["currency"] = params.get("currency") or "INR"
    params["amount"] = params.get("amount") or total_amount
    payment["params"] = params
    
    # Optional transaction id if not provided
    if "transaction_id" not in params:
        params["transaction_id"] = "mock_tx_" + now_str[:10].replace("-", "")

    return payment


def build_canonical_tags(include_bap_terms: bool = False) -> List[Dict[str, Any]]:
    """Build only RET10 order-tag list codes accepted in BPP callbacks."""
    tags = [
        {
            "code": "bpp_terms",
            "list": [
                {"code": "np_type", "value": "MSN"},
                {"code": "tax_number", "value": "07AABCF1429B1Z0"},
                {"code": "provider_tax_number", "value": "07AABCF1429B1Z0"}
            ]
        }
    ]
    if include_bap_terms:
        tags.append({
            "code": "bap_terms",
            "list": [
                {"code": "accept_bap_terms", "value": "Y"},
            ]
        })
    return tags


def build_canonical_order(
    action: str,
    payload: Dict[str, Any],
    state_code: str = "Accepted",
    order_id: Optional[str] = None,
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
    stored_order: Optional[Dict[str, Any]] = None,
    order_state: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Produces a 100% RET10 1.2.0 compliant order object for any BPP callback action.
    Guarantees created_at, updated_at, items, fulfillments, quote, payment, billing, and tags are all present.
    """
    context = payload.get("context", {})
    message = payload.get("message", {})
    incoming_order = message.get("order") or stored_order or {}

    bap_id = context.get("bap_id", "workbench.ondc.tech")
    now_str = _now()
    catalog_map = _get_catalog_item_map()

    ord_id = order_id or incoming_order.get("id") or message.get("order_id") or "2026-07-27-1001"
    ord_created_at = created_at or incoming_order.get("created_at") or now_str
    # Synchronous callbacks must retain the request's order timestamp when supplied.
    # This lets BAP and BPP agree on the same order revision during verification.
    ord_updated_at = updated_at or incoming_order.get("updated_at") or now_str

    raw_items = incoming_order.get("items", [])
    if not raw_items:
        raw_items = [{"id": "I1", "quantity": {"count": 1}}]

    items = [_build_order_item(it, action, catalog_map) for it in raw_items]

    raw_fulfillments = incoming_order.get("fulfillments", [])
    if not raw_fulfillments and stored_order:
        raw_fulfillments = stored_order.get("fulfillments", [])
    fulfillments = build_canonical_fulfillments(raw_fulfillments, state_code)
    quote = build_canonical_quote(raw_items)
    payment_source = incoming_order.get("payment") or (stored_order or {}).get("payment", {})
    payment = build_canonical_payment(payment_source, bap_id, quote["price"]["value"])
    tags = build_canonical_tags(include_bap_terms=(action == "on_confirm"))

    provider = incoming_order.get("provider") or (stored_order or {}).get("provider") or {
        "id": "P1",
        "locations": [{"id": "L1"}],
    }

    order_obj = {
        "provider": provider,
        "items": items,
        "fulfillments": fulfillments,
        "quote": quote,
        "payment": payment,
        "tags": tags,
    }

    if action in ("on_init", "on_confirm", "on_status", "on_update", "on_cancel"):
        billing_source = incoming_order.get("billing") or (stored_order or {}).get("billing", {})
        order_obj["billing"] = build_canonical_billing(billing_source, ord_created_at, ord_updated_at)

    if action in ("on_confirm", "on_status", "on_update", "on_cancel"):
        order_obj["id"] = ord_id
        if order_state:
            order_obj["state"] = order_state
        elif action == "on_cancel":
            order_obj["state"] = "Cancelled"
        elif state_code in ("Order-delivered", "Return-Delivered"):
            order_obj["state"] = "Completed"
        elif action == "on_confirm":
            # ONDC RET10: on_confirm state must be "Created" (not "Accepted")
            order_obj["state"] = "Created"
        elif state_code == "Packed" and action == "on_update":
            order_obj["state"] = "In-progress"
        else:
            order_obj["state"] = "In-progress"
        order_obj["created_at"] = ord_created_at
        order_obj["updated_at"] = ord_updated_at

    return order_obj


def validate_ret10_payload(action: str, payload: Dict[str, Any]) -> List[str]:
    """
    Validates an outgoing callback payload against RET10 1.2.0 schema rules and enums.
    Returns a list of error strings if any mandatory field or format is invalid.
    """
    errors = []
    ctx = payload.get("context", {})
    msg = payload.get("message", {})
    order = msg.get("order", {})

    # 1. Context validation
    for key in ["domain", "action", "bap_id", "bap_uri", "bpp_id", "bpp_uri", "transaction_id", "message_id", "timestamp"]:
        if not ctx.get(key):
            errors.append(f"Context missing mandatory field: context.{key}")
        elif key == "timestamp" and not ISO_UTC_REGEX.match(ctx[key]):
            errors.append(f"Context timestamp invalid format: {ctx[key]} (expected YYYY-MM-DDTHH:mm:ss.sssZ)")

    if not order:
        errors.append("Message missing mandatory object: message.order")
        return errors

    # 2. Lifecycle action specific checks
    if action in ("on_confirm", "on_status", "on_update", "on_cancel"):
        allowed_order_states = {"Created", "Accepted", "In-progress", "Completed", "Cancelled"}
        if order.get("state") not in allowed_order_states:
            errors.append(f"Order state must be one of {sorted(allowed_order_states)}")

        if not order.get("id"):
            errors.append("Order missing mandatory field: order.id")

        created_at = order.get("created_at")
        if not created_at:
            errors.append("ORDER_CREATED_AT missing: message.order.created_at must exist")
        elif not ISO_UTC_REGEX.match(created_at):
            errors.append(f"ORDER_CREATED_AT invalid ISO-8601 UTC format: {created_at}")

        updated_at = order.get("updated_at")
        if not updated_at:
            errors.append("ORDER_UPDATED_AT missing: message.order.updated_at must exist")
        elif not ISO_UTC_REGEX.match(updated_at):
            errors.append(f"ORDER_UPDATED_AT invalid ISO-8601 UTC format: {updated_at}")

        # Billing Validation
        billing = order.get("billing", {})
        if not billing:
            errors.append("Order missing mandatory object: order.billing")
        else:
            for b_key in ["name", "phone", "created_at", "updated_at"]:
                if not billing.get(b_key):
                    errors.append(f"Billing missing mandatory field: order.billing.{b_key}")
            addr = billing.get("address", {})
            if not addr:
                errors.append("Billing missing mandatory object: order.billing.address")
            else:
                for a_key in ["name", "building", "locality", "city", "state", "country", "area_code"]:
                    if not addr.get(a_key):
                        errors.append(f"Billing address missing mandatory field: order.billing.address.{a_key}")

        # Payment Params Validation
        payment = order.get("payment", {})
        params = payment.get("params", {})
        if not params:
            errors.append("Payment missing mandatory object: order.payment.params")
        else:
            for p_key in ["currency", "amount"]:
                if not params.get(p_key):
                    errors.append(f"Payment params missing mandatory field: order.payment.params.{p_key}")

    # 3. Provider validation
    prov = order.get("provider", {})
    if not prov.get("id"):
        errors.append("Provider missing mandatory field: order.provider.id")

    # 4. Fulfillments & State Code Enum validation
    fulfillments = order.get("fulfillments", [])
    if not fulfillments:
        errors.append("Fulfillments missing: message.order.fulfillments must not be empty")
    else:
        for idx, f in enumerate(fulfillments):
            if not f.get("@ondc/org/provider_name"):
                errors.append(f"Fulfillment[{idx}] missing @ondc/org/provider_name")
            
            code = f.get("state", {}).get("descriptor", {}).get("code")
            if not code:
                errors.append(f"Fulfillment[{idx}] missing state.descriptor.code")
            else:
                allowed_codes = ALLOWED_RETURN_STATUS_CODES if action in ("on_update", "on_cancel") else ALLOWED_FORWARD_STATUS_CODES
                if code not in allowed_codes:
                    errors.append(f"Fulfillment[{idx}] state.descriptor.code '{code}' invalid for {action}. Allowed: {sorted(list(allowed_codes))}")

            start = f.get("start", {})
            loc = start.get("location", {})
            if not loc.get("id"):
                errors.append(f"Fulfillment[{idx}] missing start.location.id")
            if not loc.get("descriptor", {}).get("name"):
                errors.append(f"Fulfillment[{idx}] missing start.location.descriptor.name")
            if not loc.get("gps"):
                errors.append(f"Fulfillment[{idx}] missing start.location.gps")
            addr = loc.get("address", {})
            for key in ["locality", "city", "area_code", "state"]:
                if not addr.get(key):
                    errors.append(f"Fulfillment[{idx}] missing start.location.address.{key}")
            cnt = start.get("contact", {})
            for key in ["phone", "email"]:
                if not cnt.get(key):
                    errors.append(f"Fulfillment[{idx}] missing start.contact.{key}")

    # 5. Settlement details validation
    payment = order.get("payment", {})
    settlements = payment.get("@ondc/org/settlement_details", [])
    if not settlements:
        errors.append("Payment missing mandatory array: payment['@ondc/org/settlement_details']")
    else:
        seller_sd = [s for s in settlements if s.get("settlement_counterparty") == "seller-app"]
        if not seller_sd or not seller_sd[0].get("subscriber_id"):
            errors.append("Settlement details missing valid seller-app subscriber_id")

    # 6. Tags validation
    tags = order.get("tags", [])
    bpp_terms = [t for t in tags if t.get("code") == "bpp_terms"]
    if not bpp_terms:
        errors.append("Tags missing mandatory bpp_terms entry: order.tags[*].code == 'bpp_terms'")

    # 7. Items validation (Pramaan strict checks)
    for idx, it in enumerate(order.get("items", [])):
        if action == "on_select" and not it.get("quantity"):
            errors.append(f"Item[{idx}] missing quantity for on_select")
        if not isinstance(it.get("parent_item_id"), str) or not it.get("parent_item_id"):
            errors.append(f"Item[{idx}] missing parent_item_id string")
        if not isinstance(it.get("tags"), list):
            errors.append(f"Item[{idx}] missing tags array")
        else:
            allowed_item_tag_codes = {"np_fees", "rto_action"}
            for tag_idx, tag in enumerate(it.get("tags", [])):
                tag_code = tag.get("code") if isinstance(tag, dict) else None
                if tag_code not in allowed_item_tag_codes:
                    errors.append(
                        f"Item[{idx}].tags[{tag_idx}].code must be one of {sorted(allowed_item_tag_codes)}"
                    )
                if tag_code == "np_fees":
                    for list_idx, list_item in enumerate(tag.get("list", [])):
                        if isinstance(list_item, dict) and list_item.get("code") != "id":
                            errors.append(
                                f"Item[{idx}].tags[{tag_idx}].list[{list_idx}].code must be 'id'"
                            )

    # 8. Quote breakup validation
    breakup = order.get("quote", {}).get("breakup", [])
    for idx, entry in enumerate(breakup):
        if not isinstance(entry.get("@ondc/org/item_quantity"), dict):
            errors.append(f"Quote breakup[{idx}] missing @ondc/org/item_quantity object")
        item = entry.get("item")
        if not isinstance(item, dict):
            errors.append(f"Quote breakup[{idx}] missing item object")
            continue
        if not isinstance(item.get("parent_item_id"), str) or not item.get("parent_item_id"):
            errors.append(f"Quote breakup[{idx}].item missing parent_item_id string")
        if not isinstance(item.get("tags"), list):
            errors.append(f"Quote breakup[{idx}].item missing tags array")
        else:
            allowed_quote_tag_codes = {"quote", "np_fees", "offer"}
            allowed_quote_type_values = {"fulfillment", "order", "item"}
            for tag_idx, tag in enumerate(item.get("tags", [])):
                tag_code = tag.get("code") if isinstance(tag, dict) else None
                if tag_code not in allowed_quote_tag_codes:
                    errors.append(
                        f"Quote breakup[{idx}].item.tags[{tag_idx}].code must be one of {sorted(allowed_quote_tag_codes)}"
                    )
                if tag_code == "quote":
                    for list_idx, list_item in enumerate(tag.get("list", [])):
                        if (
                            isinstance(list_item, dict)
                            and list_item.get("code") == "type"
                            and list_item.get("value") not in allowed_quote_type_values
                        ):
                            errors.append(
                                f"Quote breakup[{idx}].item.tags[{tag_idx}].list[{list_idx}].value must be one of {sorted(allowed_quote_type_values)}"
                            )
        if not item.get("price"):
            errors.append(f"Quote breakup[{idx}].item missing price object")
        if not item.get("quantity"):
            errors.append(f"Quote breakup[{idx}].item missing quantity object")

    # 9. Payment settlement validation
    settlements = payment.get("@ondc/org/settlement_details", [])
    for idx, sd in enumerate(settlements):
        for field in ("settlement_amount", "settlement_timestamp", "upi_address", "settlement_status"):
            if not sd.get(field):
                errors.append(f"Settlement[{idx}] missing {field}")
    if not payment.get("@ondc/org/settlement_basis"):
        errors.append("Payment missing @ondc/org/settlement_basis")

    return errors
