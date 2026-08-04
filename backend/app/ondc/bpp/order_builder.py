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


def _now() -> str:
    """Return ISO-8601 UTC timestamp in format YYYY-MM-DDTHH:mm:ss.sssZ."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def build_canonical_quote(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the full ONDC-compliant quote from catalog data."""
    from app.ondc.bpp.services.search import bpp_search_service
    catalog_items = bpp_search_service.mock_catalog.get("bpp/providers", [])[0].get("items", [])
    item_map = {item["id"]: item for item in catalog_items}

    quote_breakup = []
    total_value = 0.0

    for item in items:
        item_id = item.get("id")
        quantity = item.get("quantity", {}).get("selected", {}).get("count") or \
                   item.get("quantity", {}).get("count", 1)
        catalog_item = item_map.get(item_id)
        if catalog_item:
            price = float(catalog_item["price"]["value"])
            item_total = price * quantity
            total_value += item_total
            max_count = catalog_item.get("quantity", {}).get("maximum", {}).get("count", 5)
            avail_count = catalog_item.get("quantity", {}).get("available", {}).get("count", 100)
            quote_breakup.append({
                "@ondc/org/item_id": item_id,
                "@ondc/org/item_quantity": {"count": int(quantity)},
                "title": catalog_item["descriptor"]["name"],
                "@ondc/org/title_type": "item",
                "price": {"currency": "INR", "value": f"{item_total:.2f}"},
                "item": {
                    "price": {"currency": "INR", "value": f"{price:.2f}"},
                    "quantity": {
                        "available": {"count": str(avail_count)},
                        "maximum": {"count": str(max_count)}
                    }
                }
            })

    delivery_charge = 50.0
    total_value += delivery_charge
    quote_breakup.append({
        "@ondc/org/item_id": "F1",
        "title": "Delivery charges",
        "@ondc/org/title_type": "delivery",
        "price": {"currency": "INR", "value": f"{delivery_charge:.2f}"}
    })

    return {
        "price": {"currency": "INR", "value": f"{total_value:.2f}"},
        "breakup": quote_breakup,
        "ttl": "PT15M"
    }


def build_canonical_fulfillments(raw_fulfillments: List[Dict[str, Any]], state_code: str) -> List[Dict[str, Any]]:
    """Enrich fulfillment objects with all mandatory RET10 start/end/state fields."""
    if not raw_fulfillments:
        raw_fulfillments = [{}]

    enriched = []
    for f in raw_fulfillments:
        f_copy = dict(f) if f else {}
        f_copy["id"] = f_copy.get("id", "F1")
        if state_code.startswith("Return") or state_code == "Liquidated":
            f_copy["type"] = "Return"
        else:
            f_copy["type"] = f_copy.get("type", "Delivery")
        f_copy["@ondc/org/provider_name"] = f_copy.get("@ondc/org/provider_name") or "FromNear Store"
        f_copy["tracking"] = f_copy.get("tracking", False)
        f_copy["@ondc/org/category"] = f_copy.get("@ondc/org/category") or "Standard Delivery"
        f_copy["@ondc/org/TAT"] = f_copy.get("@ondc/org/TAT") or "PT45M"
        f_copy["state"] = {"descriptor": {"code": state_code}}

        # Start location & contact (Store side details)
        start = dict(f_copy.get("start", {}))
        loc = dict(start.get("location", {}))
        loc["id"] = loc.get("id") or "L1"
        desc = dict(loc.get("descriptor", {}))
        desc["name"] = desc.get("name") or "FromNear Main Branch"
        loc["descriptor"] = desc
        loc["gps"] = loc.get("gps") or "12.9715987,77.5945627"

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

        f_copy["start"] = start

        # End location & contact (Buyer side details)
        if "end" not in f_copy or not f_copy.get("end"):
            f_copy["end"] = {
                "location": {
                    "gps": "12.9715987,77.5945627",
                    "address": {"area_code": "560001"}
                },
                "contact": {
                    "phone": "9876543210",
                    "email": "buyer@example.com"
                }
            }

        enriched.append(f_copy)

    return enriched


def build_canonical_billing(raw_billing: Dict[str, Any], created_at: str, updated_at: str) -> Dict[str, Any]:
    """Construct complete RET10 compliant billing structure with all required address fields."""
    billing = dict(raw_billing) if raw_billing else {}
    billing["name"] = billing.get("name") or "John Doe"
    billing["phone"] = billing.get("phone") or "9876543210"
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

    incoming_settlements = payment.get("@ondc/org/settlement_details", [])
    settlement_details = [
        {
            "settlement_counterparty": "seller-app",
            "settlement_phase": "sale-amount",
            "settlement_type": "neft",
            "subscriber_id": bpp_id,
            "beneficiary_name": "FromNear Store",
            "bank_name": "Mock Bank",
            "branch_name": "MG Road",
            "settlement_bank_account_no": "1234567890",
            "settlement_ifsc_code": "MOCK0001234"
        }
    ]

    for sd in incoming_settlements:
        sd_copy = dict(sd)
        if sd_copy.get("settlement_counterparty") == "buyer-app":
            sd_copy["subscriber_id"] = bap_id
            settlement_details.append(sd_copy)
        elif sd_copy.get("settlement_counterparty") == "seller-app":
            sd_copy["subscriber_id"] = bpp_id
            settlement_details[0] = sd_copy

    payment["@ondc/org/settlement_details"] = settlement_details
    if "@ondc/org/buyer_app_finder_fee_type" not in payment:
        payment["@ondc/org/buyer_app_finder_fee_type"] = "percent"
    if "@ondc/org/buyer_app_finder_fee_amount" not in payment:
        payment["@ondc/org/buyer_app_finder_fee_amount"] = "3"
    if "type" not in payment:
        payment["type"] = "ON-ORDER"
    if "status" not in payment:
        payment["status"] = "PAID"
    if "collected_by" not in payment:
        payment["collected_by"] = "BAP"

    params = dict(payment.get("params", {}))
    params["currency"] = params.get("currency") or "INR"
    params["amount"] = params.get("amount") or total_amount
    payment["params"] = params

    return payment


def build_canonical_tags(include_bap_terms: bool = False) -> List[Dict[str, Any]]:
    """Build mandatory tags containing bpp_terms and optional bap_terms."""
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
                {"code": "accept_bpp_terms", "value": "Y"}
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
) -> Dict[str, Any]:
    """
    Produces a 100% RET10 1.2.0 compliant order object for any BPP callback action.
    Guarantees created_at, updated_at, items, fulfillments, quote, payment, billing, and tags are all present.
    """
    context = payload.get("context", {})
    message = payload.get("message", {})
    incoming_order = message.get("order", {})

    bap_id = context.get("bap_id", "workbench.ondc.tech")
    now_str = _now()

    ord_id = order_id or incoming_order.get("id") or "2026-07-27-1001"
    ord_created_at = created_at or incoming_order.get("created_at") or now_str
    ord_updated_at = updated_at or now_str

    # Process items
    raw_items = incoming_order.get("items", [])
    if not raw_items:
        raw_items = [{"id": "I1", "quantity": {"count": 1}}]

    if action == "on_select":
        items = []
        for it in raw_items:
            qty = it.get("quantity", {}).get("selected", {}).get("count") or \
                  it.get("quantity", {}).get("count", 1)
            items.append({
                "id": it.get("id", "I1"),
                "fulfillment_ids": ["F1"],
                "location_ids": ["L1"],
                "quantity": {"selected": {"count": int(qty)}}
            })
    else:
        items = []
        for it in raw_items:
            qty = it.get("quantity", {}).get("selected", {}).get("count") or \
                  it.get("quantity", {}).get("count", 1)
            items.append({
                "id": it.get("id", "I1"),
                "fulfillment_id": "F1",
                "quantity": {"count": int(qty)}
            })

    fulfillments = build_canonical_fulfillments(incoming_order.get("fulfillments", []), state_code)
    quote = build_canonical_quote(raw_items)
    payment = build_canonical_payment(incoming_order.get("payment", {}), bap_id, quote["price"]["value"])
    tags = build_canonical_tags(include_bap_terms=(action == "on_confirm"))

    order_obj = {
        "provider": incoming_order.get("provider", {"id": "P1", "locations": [{"id": "L1"}]}),
        "items": items,
        "fulfillments": fulfillments,
        "quote": quote,
        "payment": payment,
        "tags": tags
    }

    if action in ("on_init", "on_confirm", "on_status", "on_update", "on_cancel"):
        order_obj["billing"] = build_canonical_billing(incoming_order.get("billing", {}), ord_created_at, ord_updated_at)

    if action in ("on_confirm", "on_status", "on_update", "on_cancel"):
        order_obj["id"] = ord_id
        order_obj["state"] = "Cancelled" if action == "on_cancel" else ("Completed" if state_code in ("Order-delivered", "Return-Delivered") else ("Accepted" if action == "on_confirm" else "In-progress"))
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

    return errors
