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
    def build(cls, query: str, transaction_id: str, message_id: str) -> Dict[str, Any]:
        context = cls.generate_context("search", transaction_id, message_id)
        return {
            "context": context,
            "message": {
                "intent": {
                    "item": {"descriptor": {"name": query}},
                    "fulfillment": {"type": "Delivery"},
                }
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
                "quantity": {"count": it.get("quantity", 1)}
            })

        return {
            "context": context,
            "message": {
                "order": {
                    "provider": {"id": provider_id},
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
                "quantity": {"count": it.get("quantity", 1)}
            })

        return {
            "context": context,
            "message": {
                "order": {
                    "provider": {"id": provider_id},
                    "items": ondc_items,
                    "billing": {
                        "name": billing_address.get("name", ""),
                        "phone": billing_address.get("phone", ""),
                        "address": {
                            "door": billing_address.get("house", ""),
                            "street": billing_address.get("street", ""),
                            "city": billing_address.get("city", ""),
                            "state": billing_address.get("state", ""),
                            "area_code": billing_address.get("pincode", ""),
                        }
                    },
                    "fulfillments": [
                        {
                            "end": {
                                "contact": {
                                    "name": shipping_address.get("name", ""),
                                    "phone": shipping_address.get("phone", ""),
                                },
                                "location": {
                                    "gps": "12.9716,77.5946",
                                    "address": {
                                        "door": shipping_address.get("house", ""),
                                        "street": shipping_address.get("street", ""),
                                        "city": shipping_address.get("city", ""),
                                        "state": shipping_address.get("state", ""),
                                        "area_code": shipping_address.get("pincode", ""),
                                    }
                                }
                            }
                        }
                    ]
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
    ) -> Dict[str, Any]:
        context = cls.generate_context("confirm", transaction_id, message_id, bpp_id, bpp_uri)
        
        ondc_items = []
        for it in items:
            ondc_items.append({
                "id": it["id"],
                "quantity": {"count": it.get("quantity", 1)}
            })

        return {
            "context": context,
            "message": {
                "order": {
                    "provider": {"id": provider_id},
                    "items": ondc_items,
                    "billing": {
                        "name": billing_address.get("name", ""),
                        "phone": billing_address.get("phone", ""),
                        "address": {
                            "door": billing_address.get("house", ""),
                            "street": billing_address.get("street", ""),
                            "city": billing_address.get("city", ""),
                            "state": billing_address.get("state", ""),
                            "area_code": billing_address.get("pincode", ""),
                        }
                    },
                    "fulfillments": [
                        {
                            "end": {
                                "contact": {
                                    "name": shipping_address.get("name", ""),
                                    "phone": shipping_address.get("phone", ""),
                                },
                                "location": {
                                    "gps": "12.9716,77.5946",
                                    "address": {
                                        "door": shipping_address.get("house", ""),
                                        "street": shipping_address.get("street", ""),
                                        "city": shipping_address.get("city", ""),
                                        "state": shipping_address.get("state", ""),
                                        "area_code": shipping_address.get("pincode", ""),
                                    }
                                }
                            }
                        }
                    ],
                    "payment": {
                        "uri": "https://ondc.transaction.com/payment",
                        "status": "PAID",
                        "type": "POST-DELIVERY",
                        "params": {
                            "currency": "INR",
                            "transaction_id": transaction_id,
                            "amount": str(amount),
                        }
                    }
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
    ) -> Dict[str, Any]:
        context = cls.generate_context("track", transaction_id, message_id, bpp_id, bpp_uri)
        return {
            "context": context,
            "message": {
                "order_id": order_id
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
