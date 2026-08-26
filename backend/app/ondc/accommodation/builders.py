import datetime
from datetime import timezone
from typing import Any, Dict, List, Optional

from app.ondc.accommodation.profile import AccommodationBuyerProfile
from app.ondc.protocol.validator import ONDCValidator


class AccommodationRequestBuilder:
    def __init__(self, profile: AccommodationBuyerProfile):
        self.profile = profile

    def context(
        self,
        action: str,
        transaction_id: str,
        message_id: str,
        bpp_id: Optional[str] = None,
        bpp_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        context = {
            "domain": self.profile.domain,
            "country": self.profile.country,
            "city": self.profile.city,
            "action": action,
            "core_version": self.profile.version,
            "version": self.profile.version,
            "bap_id": self.profile.subscriber_id,
            "subscriber_id": self.profile.subscriber_id,
            "subscriberID": self.profile.subscriber_id,
            "bap_uri": self.profile.subscriber_uri,
            "location": {
                "country": {"code": self.profile.country},
                "city": {"code": self.profile.city},
            },
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

    def search(
        self,
        *,
        transaction_id: str,
        message_id: str,
        location: Optional[str] = None,
        check_in: Optional[str] = None,
        check_out: Optional[str] = None,
        guests: Optional[int] = None,
        rooms: Optional[int] = None,
        city: Optional[str] = None,
        bpp_id: Optional[str] = None,
        bpp_uri: Optional[str] = None,
        tags: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        context = self.context("search", transaction_id, message_id, bpp_id, bpp_uri)
        if city:
            context["city"] = city
            context["location"]["city"]["code"] = city

        intent: Dict[str, Any] = {
            "fulfillment": {"type": "Stay"},
            "category": {"descriptor": {"code": "HOTEL"}},
            "payment": {
                "type": "ON-ORDER",
                "status": "NOT-PAID",
                "collected_by": "BPP",
                "@ondc/org/buyer_app_finder_fee_type": "percent",
                "@ondc/org/buyer_app_finder_fee_amount": "3",
                "@ondc/org/settlement_window": "PT1D",
            },
        }
        intent["location"] = {
            "country": {"code": "IND"},
            "city": {"code": city or self.profile.city},
        }
        if location:
            intent["location"]["descriptor"] = {"name": location}

        stay_tags = []
        if check_in:
            stay_tags.append({"code": "check_in", "value": check_in})
        if check_out:
            stay_tags.append({"code": "check_out", "value": check_out})
        if guests is not None:
            stay_tags.append({"code": "guests", "value": str(guests)})
        if rooms is not None:
            stay_tags.append({"code": "rooms", "value": str(rooms)})

        all_tags = list(tags or [])
        if stay_tags:
            all_tags.append({"code": "stay", "list": stay_tags})
        if stay_tags:
            intent["tags"] = [{
                "descriptor": {"code": "BAP_TERMS"},
                "list": [{
                    "descriptor": {"code": "STATIC_TERMS"},
                    "value": ";".join(f"{item['code']}={item['value']}" for item in stay_tags),
                }],
            }]
        elif all_tags:
            intent["tags"] = [{
                "descriptor": {"code": "BAP_TERMS"},
                "list": [{"descriptor": {"code": "STATIC_TERMS"}, "value": str(all_tags)}],
            }]

        return self.validate({"context": context, "message": {"intent": intent}})

    def action_with_order(
        self,
        *,
        action: str,
        transaction_id: str,
        message_id: str,
        bpp_id: str,
        bpp_uri: str,
        order: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self.validate(
            {
                "context": self.context(action, transaction_id, message_id, bpp_id, bpp_uri),
                "message": {"order": order},
            }
        )

    def action_with_order_id(
        self,
        *,
        action: str,
        transaction_id: str,
        message_id: str,
        bpp_id: str,
        bpp_uri: str,
        order_id: str,
        extra_message: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        message = {"order_id": order_id}
        if extra_message:
            message.update(extra_message)
        return self.validate(
            {
                "context": self.context(action, transaction_id, message_id, bpp_id, bpp_uri),
                "message": message,
            }
        )

    @staticmethod
    def validate(payload: Dict[str, Any]) -> Dict[str, Any]:
        ONDCValidator.validate(payload)
        return payload
