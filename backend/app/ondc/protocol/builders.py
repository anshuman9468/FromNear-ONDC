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
        ONDCValidator.validate(payload)
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
            item_dict = {
                "id": it["id"],
                "quantity": {"count": get_item_count(it.get("quantity", 1))},
                "location_id": "L1"
            }
            if it.get("parent_item_id"):
                item_dict["parent_item_id"] = it["parent_item_id"]
            if it.get("tags"):
                item_dict["tags"] = it["tags"]
            ondc_items.append(item_dict)

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
                        {
                            "type": "Delivery",
                            "end": {
                                "location": {
                                    "gps": format_gps("12.9716,77.5946"),
                                    "address": {"area_code": "560001"}
                                }
                            }
                        }
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
            item_dict = {
                "id": it["id"],
                "quantity": {"count": get_item_count(it.get("quantity", 1))},
                "fulfillment_id": it.get("fulfillment_id", "F1")
            }
            if it.get("parent_item_id"):
                item_dict["parent_item_id"] = it["parent_item_id"]
            if it.get("tags"):
                item_dict["tags"] = it["tags"]
            ondc_items.append(item_dict)

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
                            "tracking": False,
                            "end": {
                                "contact": {
                                    "phone": shipping_address.get("phone", ""),
                                    "email": shipping_address.get("email", "buyer@example.com"),
                                    "name": shipping_address.get("name", ""),
                                },
                                "location": {
                                    "gps": format_gps("12.9716,77.5946"),
                                    "address": {
                                        "name": shipping_address.get("name", ""),
                                        "building": shipping_address.get("house", ""),
                                        "locality": shipping_address.get("street", ""),
                                        "city": shipping_address.get("city", ""),
                                        "state": shipping_address.get("state", ""),
                                        "country": "IND",
                                        "area_code": shipping_address.get("pincode", ""),
                                    }
                                }
                            }
                        }
                    ],
                    "payment": {
                        "type": "ON-ORDER",
                        "collected_by": "BAP",
                        "status": "PAID",
                        "@ondc/org/buyer_app_finder_fee_type": "percent",
                        "@ondc/org/buyer_app_finder_fee_amount": "3",
                        "@ondc/org/settlement_window": "PT1D",
                        "@ondc/org/withholding_amount": "0.0",
                        "@ondc/org/settlement_details": [
                            {
                                "settlement_counterparty": "seller-app",
                                "settlement_phase": "sale-amount",
                                "settlement_type": "neft",
                                "settlement_reference": transaction_id,
                                "settlement_bank_account_no": "XXXXXXXXXX",
                                "settlement_ifsc_code": "XXXXXXXXX",
                                "beneficiary_name": "Test Name",
                                "bank_name": "Test Bank",
                                "branch_name": "Test Branch"
                            }
                        ]
                    }
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
        
        # Sanitize items
        items_with_tags = []
        for it in (items or []):
            it_copy = dict(it)
            if "location_id" not in it_copy or not it_copy["location_id"]:
                it_copy["location_id"] = "L1"
            if "parent_item_id" in it_copy:
                if not it_copy["parent_item_id"]:
                    it_copy.pop("parent_item_id")
            if "tags" in it_copy:
                if not it_copy["tags"]:
                    it_copy.pop("tags")
            
            count_val = get_item_count(it_copy.get("quantity"))
            it_copy["quantity"] = {"count": int(count_val)}
            items_with_tags.append(it_copy)

        # Sanitize fulfillments
        fulfillments_with_tags = []
        for f in (fulfillments or []):
            f_copy = dict(f)
            # Sanitize GPS precision in fulfillments
            for loc_key in ["start", "end"]:
                if loc_key in f_copy and isinstance(f_copy[loc_key], dict):
                    loc_obj = f_copy[loc_key].get("location")
                    if isinstance(loc_obj, dict) and "gps" in loc_obj:
                        loc_obj["gps"] = format_gps(loc_obj["gps"])
            if "tags" in f_copy:
                if not f_copy["tags"]:
                    f_copy.pop("tags")
            fulfillments_with_tags.append(f_copy)

        # Sanitize quote
        if quote and isinstance(quote.get("breakup"), list):
            for entry in quote["breakup"]:
                if not isinstance(entry, dict):
                    continue
                title_type = entry.get("@ondc/org/title_type")
                item_id = entry.get("@ondc/org/item_id")
                
                if title_type == "item" or item_id:
                    item_details = entry.get("item")
                    if not isinstance(item_details, dict):
                        item_details = {}
                    
                    if "id" not in item_details or not item_details["id"]:
                        item_details["id"] = item_id or "I1"
                    
                    if "parent_item_id" in item_details:
                        if not item_details["parent_item_id"]:
                            item_details.pop("parent_item_id")
                    
                    if "price" not in item_details or not isinstance(item_details["price"], dict):
                        entry_price = entry.get("price", {})
                        item_details["price"] = {
                            "currency": entry_price.get("currency") or "INR",
                            "value": entry_price.get("value") or "0.0"
                        }
                    
                    if "tags" in item_details:
                        if not item_details["tags"]:
                            item_details.pop("tags")
                    
                    entry["item"] = item_details

        # Sanitize payment
        pay_dict = dict(payment) if payment else {}
        payment_type = pay_dict.get("type") or "ON-ORDER"
        payment_status = "PAID" if payment_type == "ON-ORDER" else (pay_dict.get("status") or "NOT-PAID")
        
        incoming_settlements = pay_dict.get("@ondc/org/settlement_details", [])
        settlement_details = []
        if incoming_settlements:
            for sd in incoming_settlements:
                sd_copy = dict(sd)
                if "settlement_counterparty" not in sd_copy:
                    sd_copy["settlement_counterparty"] = "seller-app"
                if "settlement_phase" not in sd_copy:
                    sd_copy["settlement_phase"] = "sale-amount"
                if "settlement_type" not in sd_copy:
                    sd_copy["settlement_type"] = "neft"
                if "settlement_reference" not in sd_copy:
                    sd_copy["settlement_reference"] = transaction_id
                if "beneficiary_name" not in sd_copy:
                    sd_copy["beneficiary_name"] = "FromNear Store"
                if "bank_name" not in sd_copy:
                    sd_copy["bank_name"] = "Mock Bank"
                if "branch_name" not in sd_copy:
                    sd_copy["branch_name"] = "MG Road"
                if "settlement_bank_account_no" not in sd_copy:
                    sd_copy["settlement_bank_account_no"] = "1234567890"
                if "settlement_ifsc_code" not in sd_copy:
                    sd_copy["settlement_ifsc_code"] = "MOCK0001234"
                settlement_details.append(sd_copy)
        else:
            settlement_details = [
                {
                    "settlement_counterparty": "seller-app",
                    "settlement_phase": "sale-amount",
                    "settlement_type": "neft",
                    "settlement_reference": transaction_id,
                    "beneficiary_name": "FromNear Store",
                    "bank_name": "Mock Bank",
                    "branch_name": "MG Road",
                    "settlement_bank_account_no": "1234567890",
                    "settlement_ifsc_code": "MOCK0001234"
                }
            ]

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

        return cls.validate_and_return({
            "context": context,
            "message": {
                "order": {
                    "id": order_id,
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
                        **pay_dict,
                        "type": payment_type,
                        "status": payment_status,
                        "collected_by": pay_dict.get("collected_by", "BPP") if pay_dict else "BPP",
                        "params": {
                            **(pay_dict.get("params", {}) if pay_dict else {}),
                            "currency": "INR",
                            "amount": str(amount),
                            "transaction_id": transaction_id,
                        },
                        "@ondc/org/settlement_window": pay_dict.get("@ondc/org/settlement_window") or "PT1D",
                        "@ondc/org/withholding_amount": pay_dict.get("@ondc/org/withholding_amount") or "0.0",
                        "@ondc/org/settlement_details": settlement_details
                    },
                    "quote": quote or {},
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
        cancellation_reason_id: str = "001",
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
        msg_order = order or {"id": order_id}
        if "id" not in msg_order:
            msg_order["id"] = order_id
        
        # Ensure items and fulfillments tags/parent_item_id are initialized
        if "items" in msg_order and isinstance(msg_order["items"], list):
            new_items = []
            for it in msg_order["items"]:
                it_copy = dict(it)
                if "parent_item_id" in it_copy:
                    if not it_copy["parent_item_id"]:
                        it_copy.pop("parent_item_id")
                if "tags" in it_copy:
                    if not it_copy["tags"]:
                        it_copy.pop("tags")
                
                count_val = get_item_count(it_copy.get("quantity"))
                it_copy["quantity"] = {"count": int(count_val)}
                new_items.append(it_copy)
            msg_order["items"] = new_items
            
        if "fulfillments" in msg_order and isinstance(msg_order["fulfillments"], list):
            new_fulfillments = []
            for f in msg_order["fulfillments"]:
                f_copy = dict(f)
                if "tags" in f_copy:
                    if not f_copy["tags"]:
                        f_copy.pop("tags")
                for loc_key in ["start", "end"]:
                    if loc_key in f_copy and isinstance(f_copy[loc_key], dict):
                        loc_obj = f_copy[loc_key].get("location")
                        if isinstance(loc_obj, dict) and "gps" in loc_obj:
                            loc_obj["gps"] = format_gps(loc_obj["gps"])
                new_fulfillments.append(f_copy)
            msg_order["fulfillments"] = new_fulfillments

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
