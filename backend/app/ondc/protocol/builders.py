import uuid
import datetime
from datetime import timezone
from typing import Dict, Any, List, Optional
from app.core.settings import settings


def format_gps(gps_str: Optional[str]) -> str:
    """Format GPS string to at least 6 decimal digits."""
    if not gps_str:
        return "12.971600,77.594600"
    parts = gps_str.split(",")
    if len(parts) == 2:
        try:
            lat = float(parts[0].strip())
            lng = float(parts[1].strip())
            return f"{lat:.6f},{lng:.6f}"
        except ValueError:
            pass
    return gps_str


def get_item_count(qty_field: Any) -> int:
    """Normalize item count, resolving nested dicts/ints."""
    if isinstance(qty_field, int):
        return qty_field
    if isinstance(qty_field, str):
        try:
            return int(qty_field)
        except ValueError:
            return 1
    if isinstance(qty_field, dict):
        return int(qty_field.get("count") or qty_field.get("selected", {}).get("count") or 1)
    return 1


def _money(value: Any, default: str = "0.00") -> str:
    """Return a non-empty decimal string, as required by RET10 price fields."""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return default


def _ret10_quote_tags(kind: str) -> List[Dict[str, Any]]:
    # The RET10 report validator applies the item-tag vocabulary to nested
    # quote breakup items. Use only the accepted type/customization values.
    value = "customization" if kind == "fulfillment" else "item"
    return [{"code": "type", "list": [{"code": "type", "value": value}]}]


def _complete_bap_item(item: Dict[str, Any], fulfillment_id: str = "F1") -> Dict[str, Any]:
    """Normalize the item shape reused by select, init, confirm, and update."""
    normalized = dict(item) if isinstance(item, dict) else {}
    normalized["id"] = str(normalized.get("id") or "I1")
    normalized["location_id"] = str(normalized.get("location_id") or normalized.get("location") or "L1")
    # RET10 request items use location_id. Do not forward the legacy location
    # field because Workbench validates the canonical representation.
    normalized.pop("location", None)
    normalized["fulfillment_id"] = str(normalized.get("fulfillment_id") or fulfillment_id)
    normalized["parent_item_id"] = str(normalized.get("parent_item_id") or "V1")
    normalized["quantity"] = {"count": get_item_count(normalized.get("quantity"))}
    if not isinstance(normalized.get("tags"), list) or not normalized["tags"]:
        normalized["tags"] = [{"code": "type", "list": [{"code": "type", "value": "item"}]}]
    return normalized


def _complete_bap_fulfillment(fulfillment: Dict[str, Any], fulfillment_id: str = "F1") -> Dict[str, Any]:
    """Fill stable contact and location defaults before an outbound BAP request."""
    normalized = dict(fulfillment) if isinstance(fulfillment, dict) else {}
    normalized["id"] = str(normalized.get("id") or fulfillment_id)
    normalized["type"] = normalized.get("type") or "Delivery"
    normalized["tracking"] = normalized.get("tracking") if isinstance(normalized.get("tracking"), bool) else True

    start = dict(normalized.get("start") or {})
    start_location = dict(start.get("location") or {})
    start_location["id"] = str(start_location.get("id") or "L1")
    start_location["gps"] = format_gps(start_location.get("gps") or "12.9716,77.5946")
    start_descriptor = dict(start_location.get("descriptor") or {})
    start_descriptor["name"] = str(start_descriptor.get("name") or "FromNear Main Branch")
    start_location["descriptor"] = start_descriptor
    start_address = dict(start_location.get("address") or {})
    start_address.update({
        "locality": str(start_address.get("locality") or "MG Road"),
        "city": str(start_address.get("city") or "Bengaluru"),
        "state": str(start_address.get("state") or "Karnataka"),
        "country": str(start_address.get("country") or "IND"),
        "area_code": str(start_address.get("area_code") or "560001"),
    })
    start_location["address"] = start_address
    start["location"] = start_location
    start_contact = dict(start.get("contact") or {})
    start_contact["phone"] = str(start_contact.get("phone") or "9876543210")
    start_contact["email"] = str(start_contact.get("email") or "support@fromnear.com")
    start["contact"] = start_contact
    normalized["start"] = start

    end = dict(normalized.get("end") or {})
    contact = dict(end.get("contact") or {})
    contact["phone"] = str(contact.get("phone") or "9876543210")
    contact["email"] = str(contact.get("email") or "buyer@example.com")
    contact["name"] = str(contact.get("name") or "Jane Doe")
    end["contact"] = contact
    person = dict(end.get("person") or {})
    person["name"] = str(person.get("name") or contact["name"])
    end["person"] = person
    location = dict(end.get("location") or {})
    location["id"] = str(location.get("id") or "L2")
    location["gps"] = format_gps(location.get("gps") or "12.9716,77.5946")
    descriptor = dict(location.get("descriptor") or {})
    descriptor["name"] = str(descriptor.get("name") or "Buyer Delivery Location")
    location["descriptor"] = descriptor
    address = dict(location.get("address") or {})
    address.update({
        "name": str(address.get("name") or contact["name"]),
        "building": str(address.get("building") or address.get("door") or "Apt 4B"),
        "locality": str(address.get("locality") or address.get("street") or "MG Road"),
        "city": str(address.get("city") or "Bengaluru"),
        "state": str(address.get("state") or "Karnataka"),
        "country": str(address.get("country") or "IND"),
        "area_code": str(address.get("area_code") or "560001"),
    })
    location["address"] = address
    end["location"] = location
    normalized["end"] = end
    normalized["tags"] = (
        normalized.get("tags")
        if isinstance(normalized.get("tags"), list) and normalized.get("tags")
        else [{"code": "order_details", "list": [{"code": "weight_unit", "value": "kilogram"}]}]
    )
    return normalized


def _complete_quote(quote: Optional[Dict[str, Any]], items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the quote shape Workbench validates on every confirm request."""
    raw_quote = dict(quote) if isinstance(quote, dict) else {}
    existing = raw_quote.get("breakup") if isinstance(raw_quote.get("breakup"), list) else []
    entries_by_item = {
        entry.get("@ondc/org/item_id"): entry
        for entry in existing
        if isinstance(entry, dict) and entry.get("@ondc/org/title_type") == "item"
    }
    delivery_entry = next(
        (
            entry for entry in existing
            if isinstance(entry, dict) and entry.get("@ondc/org/title_type") == "delivery"
        ),
        {},
    )

    breakup: List[Dict[str, Any]] = []
    total = 0.0
    for source_item in items or [{"id": "I1", "quantity": {"count": 1}}]:
        item_id = str(source_item.get("id") or "I1")
        quantity = get_item_count(source_item.get("quantity"))
        source = dict(entries_by_item.get(item_id) or {})
        source_price = source.get("price") if isinstance(source.get("price"), dict) else {}
        unit_price = _money(source_price.get("value", source_item.get("price", "250.00")), "250.00")
        line_value = _money(float(unit_price) * quantity)
        total += float(line_value)
        item = dict(source.get("item") or {})
        item["id"] = str(item.get("id") or item_id)
        item["parent_item_id"] = str(item.get("parent_item_id") or source_item.get("parent_item_id") or "V1")
        item["quantity"] = {
            "available": {"count": str(item.get("quantity", {}).get("available", {}).get("count", "99"))},
            "maximum": {"count": str(item.get("quantity", {}).get("maximum", {}).get("count", "5"))},
            "selected": {"count": quantity},
        }
        item["price"] = {"currency": "INR", "value": unit_price}
        item["tags"] = _ret10_quote_tags("item")
        breakup.append({
            "@ondc/org/item_id": item_id,
            "@ondc/org/item_quantity": {"count": quantity},
            "title": source.get("title") or item_id,
            "@ondc/org/title_type": "item",
            "price": {"currency": "INR", "value": line_value},
            "item": item,
        })

    delivery_price = _money(
        (delivery_entry.get("price") or {}).get("value") if isinstance(delivery_entry, dict) else None,
        "50.00",
    )
    total += float(delivery_price)
    delivery_item = dict((delivery_entry or {}).get("item") or {})
    delivery_item["id"] = str(delivery_item.get("id") or "F1")
    delivery_item["parent_item_id"] = str(delivery_item.get("parent_item_id") or "V1")
    delivery_item["quantity"] = {
        "available": {"count": str(delivery_item.get("quantity", {}).get("available", {}).get("count", "99"))},
        "maximum": {"count": str(delivery_item.get("quantity", {}).get("maximum", {}).get("count", "5"))},
        "selected": {"count": 1},
    }
    delivery_item["price"] = {"currency": "INR", "value": delivery_price}
    delivery_item["tags"] = _ret10_quote_tags("fulfillment")
    breakup.append({
        "@ondc/org/item_id": "F1",
        "@ondc/org/item_quantity": {"count": 1},
        "title": (delivery_entry or {}).get("title") or "Delivery charges",
        "@ondc/org/title_type": "delivery",
        "price": {"currency": "INR", "value": delivery_price},
        "item": delivery_item,
    })
    return {"price": {"currency": "INR", "value": _money(total)}, "breakup": breakup, "ttl": raw_quote.get("ttl") or "PT15M"}


def _complete_settlements(payment: Optional[Dict[str, Any]], transaction_id: str, timestamp: str) -> Dict[str, Any]:
    """Ensure settlement fields are present and typed before buyer sends confirm/update."""
    result = dict(payment) if isinstance(payment, dict) else {}
    source = result.get("@ondc/org/settlement_details")
    source = source if isinstance(source, list) and source else [{}]
    details = []
    for entry in source:
        settlement = dict(entry) if isinstance(entry, dict) else {}
        settlement["settlement_counterparty"] = settlement.get("settlement_counterparty") or "seller-app"
        settlement["settlement_phase"] = settlement.get("settlement_phase") or "sale-amount"
        settlement["settlement_type"] = settlement.get("settlement_type") or "neft"
        settlement["settlement_reference"] = settlement.get("settlement_reference") or transaction_id
        settlement["settlement_timestamp"] = str(settlement.get("settlement_timestamp") or timestamp)
        settlement["settlement_amount"] = _money(settlement.get("settlement_amount", result.get("params", {}).get("amount", "500.00")), "500.00")
        settlement["subscriber_id"] = settlement.get("subscriber_id") or settings.ONDC_SUBSCRIBER_ID
        settlement["beneficiary_name"] = settlement.get("beneficiary_name") or "FromNear Store"
        settlement["bank_name"] = settlement.get("bank_name") or "Mock Bank"
        settlement["branch_name"] = settlement.get("branch_name") or "MG Road"
        settlement["settlement_bank_account_no"] = settlement.get("settlement_bank_account_no") or "1234567890"
        settlement["settlement_ifsc_code"] = settlement.get("settlement_ifsc_code") or "MOCK0001234"
        settlement["upi_address"] = settlement.get("upi_address") or "fromnear@upi"
        settlement["settlement_status"] = settlement.get("settlement_status") or "PAID"
        details.append(settlement)
    result["@ondc/org/settlement_details"] = details
    result["@ondc/org/settlement_basis"] = result.get("@ondc/org/settlement_basis") or "delivery"
    result["@ondc/org/settlement_window"] = result.get("@ondc/org/settlement_window") or "PT1D"
    result["@ondc/org/withholding_amount"] = result.get("@ondc/org/withholding_amount") or "0.0"
    return result


def _assert_no_null_values(value: Any, path: str = "payload") -> None:
    """Prevent JSON null from reaching Workbench as an implicit undefined value."""
    if value is None:
        raise ValueError(f"Outbound ONDC payload contains null at {path}")
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_no_null_values(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_null_values(child, f"{path}[{index}]")


class BaseRequestBuilder:
    @staticmethod
    def generate_context(
        action: str,
        transaction_id: str,
        message_id: str,
        bpp_id: Optional[str] = None,
        bpp_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a compliant ONDC request context."""
        context = {
            "domain": settings.ONDC_DOMAIN,
            "country": settings.ONDC_COUNTRY,
            "city": settings.ONDC_CITY,
            "action": action,
            "core_version": "1.2.0",
            "bap_id": settings.ONDC_SUBSCRIBER_ID,
            "bap_uri": settings.ONDC_SUBSCRIBER_URI,
            "transaction_id": transaction_id,
            "message_id": message_id,
            "timestamp": datetime.datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "ttl": "PT30S",
        }
        if bpp_id:
            context["bpp_id"] = bpp_id
        if bpp_uri:
            context["bpp_uri"] = bpp_uri
        return context

    @classmethod
    def validate_and_return(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Enforces schema and structure compliance check before returning payload."""
        from app.ondc.protocol.validator import ONDCValidator
        _assert_no_null_values(payload)
        valid, errors = ONDCValidator.validate(payload)
        if not valid:
            raise ValueError(f"Outbound ONDC payload failed validation: {errors}")
        return payload


class SearchRequestBuilder(BaseRequestBuilder):
    @classmethod
    def build(
        cls,
        query: str = "",
        transaction_id: str = "",
        message_id: str = "",
        bpp_id: Optional[str] = None,
        bpp_uri: Optional[str] = None,
        mode: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        context = cls.generate_context("search", transaction_id, message_id, bpp_id, bpp_uri)
        if mode == "start" and not (start_time and end_time):
            context["city"] = "*"

        intent: Dict[str, Any] = {
            "fulfillment": {"type": "Delivery"}
        }
        if query:
            intent["item"] = {
                "descriptor": {"name": query}
            }

        intent["payment"] = {
            "type": "ON-ORDER",
            "status": "PAID",
            "collected_by": "BAP",
            "@ondc/org/buyer_app_finder_fee_type": "percent",
            "@ondc/org/buyer_app_finder_fee_amount": "3",
            "@ondc/org/settlement_window": "PT1D",
            "@ondc/org/withholding_amount": "0.0"
        }

        tags = []
        if mode:
            inc_list = [{"code": "mode", "value": mode}]
            if start_time:
                inc_list.append({"code": "start_time", "value": start_time})
            if end_time:
                inc_list.append({"code": "end_time", "value": end_time})
            tags.append({
                "code": "catalog_inc",
                "list": inc_list
            })

        if tags:
            intent["tags"] = tags

        return cls.validate_and_return({
            "context": context,
            "message": {
                "intent": intent
            },
        })


class SelectRequestBuilder(BaseRequestBuilder):
    @classmethod
    def build(
        cls,
        transaction_id: str,
        message_id: str,
        bpp_id: str,
        bpp_uri: str,
        provider_id: str,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        context = cls.generate_context("select", transaction_id, message_id, bpp_id, bpp_uri)
        
        # items format: [{"id": "item_id", "quantity": 1}]
        ondc_items = []
        for it in items:
            ondc_items.append(_complete_bap_item(it))

        return cls.validate_and_return({
            "context": context,
            "message": {
                "order": {
                    "provider": {
                        "id": provider_id,
                        "locations": [{"id": "L1"}]
                    },
                    "items": ondc_items,
                    "fulfillments": [
                        _complete_bap_fulfillment({
                            # id is MANDATORY in select per RET10 schema
                            "id": "F1",
                            "type": "Delivery",
                            # tracking must be consistent with on_select response
                            "tracking": True,
                            "end": {
                                "contact": {
                                    "phone": "9876543210",
                                    "email": "buyer@example.com",
                                    "name": "Jane Doe"
                                },
                                "person": {
                                    "name": "Jane Doe"
                                },
                                "location": {
                                    "gps": format_gps("12.9716,77.5946"),
                                    "address": {
                                        "name": "Jane Doe",
                                        "building": "Apt 4B",
                                        "locality": "MG Road",
                                        "city": "Bengaluru",
                                        "state": "Karnataka",
                                        "country": "IND",
                                        "area_code": "560001"
                                    }
                                }
                            }
                        })
                    ]
                }
            },
        })


class InitRequestBuilder(BaseRequestBuilder):
    @classmethod
    def build(
        cls,
        transaction_id: str,
        message_id: str,
        bpp_id: str,
        bpp_uri: str,
        provider_id: str,
        items: List[Dict[str, Any]],
        billing_address: Dict[str, Any],
        shipping_address: Dict[str, Any],
    ) -> Dict[str, Any]:
        context = cls.generate_context("init", transaction_id, message_id, bpp_id, bpp_uri)
        
        ondc_items = []
        for it in items:
            ondc_items.append(_complete_bap_item(it))

        return cls.validate_and_return({
            "context": context,
            "message": {
                "order": {
                    "provider": {
                        "id": provider_id,
                        "locations": [{"id": "L1"}]
                    },
                    "items": ondc_items,
                    "billing": {
                        "name": billing_address.get("name", ""),
                        "phone": billing_address.get("phone", ""),
                        "email": billing_address.get("email", "buyer@example.com"),
                        "address": {
                            "name": billing_address.get("name", ""),
                            "building": billing_address.get("house", ""),
                            "locality": billing_address.get("street", ""),
                            "city": billing_address.get("city", ""),
                            "state": billing_address.get("state", ""),
                            "country": "IND",
                            "area_code": billing_address.get("pincode", ""),
                        },
                        "created_at": context["timestamp"],
                        "updated_at": context["timestamp"],
                    },
                    "fulfillments": [
                        {
                            "id": "F1",
                            "type": "Delivery",
                            # tracking MUST be True — mirrors on_select.fulfillment.tracking value
                            "tracking": True,
                            "@ondc/org/TAT": "PT45M",
                            "@ondc/org/provider_name": "FromNear Store",
                            "tags": [],
                            "end": {
                                "contact": {
                                    "phone": shipping_address.get("phone", "") or "9876543210",
                                    "email": shipping_address.get("email", "") or "buyer@example.com",
                                    "name": shipping_address.get("name", "") or "Jane Doe",
                                },
                                "person": {
                                    "name": shipping_address.get("name", "") or "Jane Doe"
                                },
                                "location": {
                                    "id": "L2",
                                    "descriptor": {"name": "Buyer Delivery Location"},
                                    "gps": format_gps("12.9716,77.5946"),
                                    "address": {
                                        "name": shipping_address.get("name", "") or "Jane Doe",
                                        "building": shipping_address.get("house", "") or "Apt 4B",
                                        "locality": shipping_address.get("street", "") or "MG Road",
                                        "city": shipping_address.get("city", "") or "Bengaluru",
                                        "state": shipping_address.get("state", "") or "Karnataka",
                                        "country": "IND",
                                        "area_code": shipping_address.get("pincode", "") or "560001",
                                    }
                                }
                            }
                        }
                    ],
                    "payment": _complete_settlements({
                        "type": "ON-ORDER",
                        # collected_by MUST be "BPP" — must be consistent across INIT and CONFIRM
                        "collected_by": "BPP",
                        "status": "PAID",
                        "@ondc/org/buyer_app_finder_fee_type": "percent",
                        "@ondc/org/buyer_app_finder_fee_amount": "3",
                        "@ondc/org/settlement_basis": "delivery",
                        "@ondc/org/settlement_window": "PT1D",
                        "@ondc/org/withholding_amount": "0.0",
                    }, transaction_id, context["timestamp"])
                }
            },
        })


class ConfirmRequestBuilder(BaseRequestBuilder):
    @classmethod
    def build(
        cls,
        transaction_id: str,
        message_id: str,
        bpp_id: str,
        bpp_uri: str,
        provider_id: str,
        items: List[Dict[str, Any]],
        billing_address: Dict[str, Any],
        shipping_address: Dict[str, Any],
        amount: float,
        order_id: str = "",
        quote: Dict[str, Any] = None,
        payment: Dict[str, Any] = None,
        tags: List[Dict[str, Any]] = None,
        created_at: str = "",
        updated_at: str = "",
        fulfillments: List[Dict[str, Any]] = None,
        billing: Dict[str, Any] = None,
        provider: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        context = cls.generate_context("confirm", transaction_id, message_id, bpp_id, bpp_uri)
        
        # Sanitize items - parent_item_id and tags are MANDATORY per RET10
        items_with_tags = []
        for it in (items or []):
            items_with_tags.append(_complete_bap_item(it))

        # Sanitize fulfillments - ensure all mandatory RET10 fields are present
        fulfillments_with_tags = []
        for f in (fulfillments or []):
            f_copy = _complete_bap_fulfillment(f)
            # tracking is a mandatory boolean field
            if "tracking" not in f_copy:
                f_copy["tracking"] = False
            # @ondc/org/TAT is mandatory
            if not f_copy.get("@ondc/org/TAT"):
                f_copy["@ondc/org/TAT"] = "PT45M"
            # @ondc/org/provider_name is mandatory
            if not f_copy.get("@ondc/org/provider_name"):
                f_copy["@ondc/org/provider_name"] = "FromNear Store"

            # Ensure end is present and fully populated
            end = dict(f_copy.get("end", {}))

            # Contact
            end_cnt = dict(end.get("contact", {}))
            end_cnt["phone"] = end_cnt.get("phone") or shipping_address.get("phone") or "9876543210"
            end_cnt["email"] = end_cnt.get("email") or shipping_address.get("email") or "buyer@example.com"
            end_cnt["name"] = end_cnt.get("name") or shipping_address.get("name") or "Jane Doe"
            end["contact"] = end_cnt

            # Person
            end_pers = dict(end.get("person", {}))
            end_pers["name"] = end_pers.get("name") or end_cnt["name"] or "Jane Doe"
            end["person"] = end_pers

            # Location
            end_loc = dict(end.get("location", {}))
            end_loc["gps"] = format_gps(end_loc.get("gps") or "12.9716,77.5946")

            # Address
            end_addr = dict(end_loc.get("address", {}))
            end_addr["name"] = end_addr.get("name") or end_cnt["name"] or "Jane Doe"
            end_addr["building"] = end_addr.get("building") or end_addr.get("door") or shipping_address.get("house") or "Apt 4B"
            end_addr["locality"] = end_addr.get("locality") or end_addr.get("street") or shipping_address.get("street") or "MG Road"
            end_addr["city"] = end_addr.get("city") or shipping_address.get("city") or "Bengaluru"
            end_addr["state"] = end_addr.get("state") or shipping_address.get("state") or "Karnataka"
            end_addr["country"] = end_addr.get("country") or "IND"
            end_addr["area_code"] = end_addr.get("area_code") or shipping_address.get("pincode") or "560001"

            end_loc["address"] = end_addr
            end["location"] = end_loc
            f_copy["end"] = end

            # Sanitize GPS precision in start location
            if "start" in f_copy and isinstance(f_copy["start"], dict):
                start = dict(f_copy["start"])
                start_loc = dict(start.get("location", {}))
                if "gps" in start_loc:
                    start_loc["gps"] = format_gps(start_loc["gps"])
                start["location"] = start_loc
                f_copy["start"] = start

            fulfillments_with_tags.append(f_copy)

        completed_quote = _complete_quote(quote, items_with_tags)

        # Sanitize payment
        pay_dict = dict(payment) if payment else {}
        payment_type = pay_dict.get("type") or "ON-ORDER"
        payment_status = "PAID" if payment_type == "ON-ORDER" else (pay_dict.get("status") or "NOT-PAID")
        
        # Enforce all ONDC liability & dispute resolution terms
        BAP_TERMS_LIST = [
            {"code": "accept_bpp_terms", "value": "Y"},
            {"code": "max_liability", "value": "2"},
            {"code": "max_liability_cap", "value": "10000"},
            {"code": "mandatory_arbitration", "value": "y"},
            {"code": "court_jurisdiction", "value": "Bengaluru"},
            {"code": "delay_interest", "value": "1000"}
        ]

        sanitized_tags = []
        has_bap_terms = False
        for t in (tags or []):
            t_copy = dict(t)
            if t_copy.get("code") == "bap_terms":
                t_copy["list"] = BAP_TERMS_LIST
                has_bap_terms = True
            sanitized_tags.append(t_copy)
        if not has_bap_terms:
            sanitized_tags.append({"code": "bap_terms", "list": BAP_TERMS_LIST})

        completed_payment = _complete_settlements(pay_dict, transaction_id, context["timestamp"])

        return cls.validate_and_return({
            "context": context,
            "message": {
                "order": {
                    "id": order_id,
                    # RET10: BAP confirm must send state = "Created" (not "Accepted")
                    "state": "Created",
                    "created_at": created_at or context["timestamp"],
                    "updated_at": updated_at or context["timestamp"],
                    "provider": provider or {
                        "id": provider_id,
                        "locations": [{"id": "L1"}]
                    },
                    "items": items_with_tags,
                    "billing": billing or {},
                    "fulfillments": fulfillments_with_tags,
                    "payment": {
                        **completed_payment,
                        "type": payment_type,
                        "status": payment_status,
                        "collected_by": pay_dict.get("collected_by", "BPP") if pay_dict else "BPP",
                        "params": {
                            **(pay_dict.get("params", {}) if pay_dict else {}),
                            "currency": "INR",
                            "amount": str(amount),
                            "transaction_id": transaction_id,
                        },
                        # @ondc/org/settlement_basis is MANDATORY per RET10 schema
                        "@ondc/org/settlement_basis": completed_payment["@ondc/org/settlement_basis"],
                        "@ondc/org/settlement_window": completed_payment["@ondc/org/settlement_window"],
                        "@ondc/org/withholding_amount": completed_payment["@ondc/org/withholding_amount"],
                        "@ondc/org/settlement_details": completed_payment["@ondc/org/settlement_details"]
                    },
                    "quote": completed_quote,
                    "tags": sanitized_tags
                }
            },
        })


class StatusRequestBuilder(BaseRequestBuilder):
    @classmethod
    def build(
        cls,
        transaction_id: str,
        message_id: str,
        bpp_id: str,
        bpp_uri: str,
        order_id: str,
    ) -> Dict[str, Any]:
        context = cls.generate_context("status", transaction_id, message_id, bpp_id, bpp_uri)
        return cls.validate_and_return({
            "context": context,
            "message": {
                "order_id": order_id
            }
        })


class TrackRequestBuilder(BaseRequestBuilder):
    @classmethod
    def build(
        cls,
        transaction_id: str,
        message_id: str,
        bpp_id: str,
        bpp_uri: str,
        order_id: str,
        callback_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        context = cls.generate_context("track", transaction_id, message_id, bpp_id, bpp_uri)
        cb_url = callback_url or f"{settings.ONDC_SUBSCRIBER_URI.rstrip('/')}/on_track"
        return cls.validate_and_return({
            "context": context,
            "message": {
                "order_id": order_id,
                "callback_url": cb_url
            }
        })


class CancelRequestBuilder(BaseRequestBuilder):
    @classmethod
    def build(
        cls,
        transaction_id: str,
        message_id: str,
        bpp_id: str,
        bpp_uri: str,
        order_id: str,
        cancellation_reason_id: str = "002",
    ) -> Dict[str, Any]:
        context = cls.generate_context("cancel", transaction_id, message_id, bpp_id, bpp_uri)
        return cls.validate_and_return({
            "context": context,
            "message": {
                "order_id": order_id,
                "cancellation_reason_id": cancellation_reason_id,
            }
        })


class SupportRequestBuilder(BaseRequestBuilder):
    @classmethod
    def build(
        cls,
        transaction_id: str,
        message_id: str,
        bpp_id: str,
        bpp_uri: str,
        ref_id: str,
    ) -> Dict[str, Any]:
        context = cls.generate_context("support", transaction_id, message_id, bpp_id, bpp_uri)
        return cls.validate_and_return({
            "context": context,
            "message": {
                "ref_id": ref_id
            }
        })


class UpdateRequestBuilder(BaseRequestBuilder):
    @classmethod
    def build(
        cls,
        transaction_id: str,
        message_id: str,
        bpp_id: str,
        bpp_uri: str,
        order_id: str,
        update_target: str = "item",
        order: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = cls.generate_context("update", transaction_id, message_id, bpp_id, bpp_uri)
        msg_order = dict(order) if isinstance(order, dict) else {"id": order_id}
        if "id" not in msg_order:
            msg_order["id"] = order_id
        
        # Ensure items and fulfillments tags/parent_item_id are initialized
        if "items" in msg_order and isinstance(msg_order["items"], list):
            new_items = []
            for it in msg_order["items"]:
                new_items.append(_complete_bap_item(it))
            msg_order["items"] = new_items
            
        if "fulfillments" in msg_order and isinstance(msg_order["fulfillments"], list):
            new_fulfillments = []
            for f in msg_order["fulfillments"]:
                f_copy = _complete_bap_fulfillment(f)
                
                # Ensure end is present and fully populated
                end = dict(f_copy.get("end", {}))
                
                # Contact
                end_cnt = dict(end.get("contact", {}))
                end_cnt["phone"] = end_cnt.get("phone") or "9876543210"
                end_cnt["email"] = end_cnt.get("email") or "buyer@example.com"
                end_cnt["name"] = end_cnt.get("name") or "Jane Doe"
                end["contact"] = end_cnt
                
                # Person
                end_pers = dict(end.get("person", {}))
                end_pers["name"] = end_pers.get("name") or end_cnt["name"] or "Jane Doe"
                end["person"] = end_pers
                
                # Location
                end_loc = dict(end.get("location", {}))
                end_loc["gps"] = format_gps(end_loc.get("gps") or "12.9716,77.5946")
                
                # Address
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
                f_copy["end"] = end

                # Sanitize GPS precision in start location
                if "start" in f_copy and isinstance(f_copy["start"], dict):
                    start = dict(f_copy["start"])
                    start_loc = dict(start.get("location", {}))
                    if "gps" in start_loc:
                        start_loc["gps"] = format_gps(start_loc["gps"])
                    start["location"] = start_loc
                    f_copy["start"] = start

                f_copy["tags"] = f_copy.get("tags") if isinstance(f_copy.get("tags"), list) else []
                new_fulfillments.append(f_copy)
            msg_order["fulfillments"] = new_fulfillments

        if isinstance(msg_order.get("payment"), dict):
            msg_order["payment"] = _complete_settlements(
                msg_order["payment"], transaction_id, context["timestamp"]
            )

        return cls.validate_and_return({
            "context": context,
            "message": {
                "update_target": update_target,
                "order": msg_order
            }
        })


class IssueRequestBuilder(BaseRequestBuilder):
    @classmethod
    def build(
        cls,
        transaction_id: str,
        message_id: str,
        bpp_id: str,
        bpp_uri: str,
        order_id: str,
        issue_id: Optional[str] = None,
        category: str = "ITEM",
        sub_category: str = "ITM01",
        short_desc: str = "Issue with item quality",
        long_desc: str = "Detailed issue with item quality",
        order_details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = cls.generate_context("issue", transaction_id, message_id, bpp_id, bpp_uri)
        context["domain"] = settings.ONDC_DOMAIN
        iss_id = issue_id or str(uuid.uuid4())
        ts = context["timestamp"]
        ord_details = order_details or {
            "id": order_id,
            "state": "Completed",
            "items": [{"id": "I1", "quantity": {"count": 1}}],
            "fulfillments": [{"id": "F1", "state": "Order-delivered"}],
            "provider_id": "P1"
        }
        if "id" not in ord_details:
            ord_details["id"] = order_id
        return cls.validate_and_return({
            "context": context,
            "message": {
                "issue": {
                    "id": iss_id,
                    "category": category,
                    "sub_category": sub_category,
                    "bap_id": settings.ONDC_SUBSCRIBER_ID,
                    "bpp_id": bpp_id,
                    "complainant_info": {
                        "person": {"name": "Jane Doe"},
                        "contact": {
                            "phone": "9876543210",
                            "email": "buyer@example.com"
                        }
                    },
                    "order_details": ord_details,
                    "description": {
                        "short_desc": short_desc,
                        "long_desc": long_desc,
                        "additional_desc": {
                            "url": "https://ondc.fromnear.com/proof.jpg",
                            "content_type": "text/plain"
                        },
                        "images": [
                            "https://ondc.fromnear.com/proof.jpg"
                        ]
                    },
                    "source": {
                        "network_participant_id": settings.ONDC_SUBSCRIBER_ID,
                        "type": "CONSUMER"
                    },
                    "expected_response_time": {"duration": "PT2H"},
                    "expected_resolution_time": {"duration": "P1D"},
                    "status": "OPEN",
                    "issue_type": "ISSUE",
                    "issue_actions": {
                        "complainant_actions": [
                            {
                                "complainant_action": "OPEN",
                                "short_desc": "Complaint created",
                                "updated_at": ts,
                                "updated_by": {
                                    "org": {"name": f"{settings.ONDC_SUBSCRIBER_ID}::{settings.ONDC_DOMAIN}"},
                                    "contact": {
                                        "phone": "9876543210",
                                        "email": "buyer@example.com"
                                    },
                                    "person": {"name": "Jane Doe"}
                                }
                            }
                        ]
                    },
                    "created_at": ts,
                    "updated_at": ts
                }
            }
        })
