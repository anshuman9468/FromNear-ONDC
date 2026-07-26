import uuid
import datetime
from datetime import timezone
from typing import Dict, Any, List, Optional
from app.core.settings import settings


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
        intent: Dict[str, Any] = {
            "fulfillment": {"type": "Delivery"}
        }
        if query:
            intent["item"] = {"descriptor": {"name": query}}

        intent["payment"] = {
            "@ondc/org/buyer_app_finder_fee_type": "percent",
            "@ondc/org/buyer_app_finder_fee_amount": "3"
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

        return {
            "context": context,
            "message": {
                "intent": intent
            },
        }


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
            ondc_items.append({
                "id": it["id"],
                "quantity": {"count": it.get("quantity", 1)},
                "location_id": "L1"
            })

        return {
            "context": context,
            "message": {
                "order": {
                    "provider": {
                        "id": provider_id,
                        "locations": [{"id": "L1"}]
                    },
                    "items": ondc_items,
                    "fulfillments": [{"end": {"location": {"gps": "12.9716,77.5946", "address": {"area_code": "560001"}}}}]
                }
            },
        }


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
            ondc_items.append({
                "id": it["id"],
                "quantity": {"count": it.get("quantity", 1)},
                "fulfillment_id": it.get("fulfillment_id", "F1"),
            })

        return {
            "context": context,
            "message": {
                "order": {
                    "provider": {
                        "id": provider_id,
                        "locations": [{"id": "L1"}],
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
                                },
                                "location": {
                                    "gps": "12.9716,77.5946",
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
                        "@ondc/org/buyer_app_finder_fee_type": "percent",
                        "@ondc/org/buyer_app_finder_fee_amount": "3",
                        "@ondc/org/settlement_details": [
                            {
                                "settlement_counterparty": "seller-app",
                                "settlement_phase": "sale-amount",
                                "settlement_type": "upi",
                                "upi_address": "test@upi",
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
        }


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
        

        return {
            "context": context,
            "message": {
                "order": {
                    "id": order_id,
                    "state": "Created",
                    "created_at": created_at or context["timestamp"],
                    "updated_at": updated_at or context["timestamp"],
                    "provider": provider or {
                        "id": provider_id,
                        "locations": [{"id": "L1"}],
                    },
                    "items": items,
                    "billing": billing or {},
                    "fulfillments": fulfillments or [],
                    "payment": {
                        **(payment or {}),
                        "type": (payment.get("type") if (payment and payment.get("type")) else "ON-ORDER"),
                        "status": "PAID" if (payment and payment.get("collected_by") == "BAP") else (payment.get("status", "NOT-PAID") if payment else "NOT-PAID"),
                        "collected_by": payment.get("collected_by", "BPP") if payment else "BPP",
                        "params": {
                            **(payment.get("params", {}) if payment else {}),
                            "currency": "INR",
                            "amount": str(amount),
                            "transaction_id": transaction_id,
                        }
                    },
                    "quote": quote or {},
                    "tags": (
                        tags + [{"code": "bap_terms", "list": [{"code": "accept_bpp_terms", "value": "Y"}]}]
                        if tags and not any(t.get("code") == "bap_terms" for t in tags)
                        else (tags or [{"code": "bap_terms", "list": [{"code": "accept_bpp_terms", "value": "Y"}]}])
                    )
                }
            },
        }



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
        return {
            "context": context,
            "message": {
                "order_id": order_id
            }
        }


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
        return {
            "context": context,
            "message": {
                "order_id": order_id,
                "callback_url": cb_url
            }
        }


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
        return {
            "context": context,
            "message": {
                "order_id": order_id,
                "cancellation_reason_id": cancellation_reason_id,
            }
        }


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
        return {
            "context": context,
            "message": {
                "ref_id": ref_id
            }
        }


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
        return {
            "context": context,
            "message": {
                "update_target": update_target,
                "order": msg_order
            }
        }


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
            "items": [{"id": "I1", "quantity": 1}],
            "fulfillments": [{"id": "F1", "state": "Order-delivered"}],
            "provider_id": "P1"
        }
        if "id" not in ord_details:
            ord_details["id"] = order_id
        return {
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
        }
