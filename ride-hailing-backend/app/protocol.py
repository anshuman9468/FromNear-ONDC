from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .config import settings


CALLBACK_ACTIONS = (
    "on_search", "on_select", "on_init", "on_confirm", "on_status",
    "on_track", "on_cancel", "on_update", "on_support", "on_issue",
    "on_issue_status",
)


def context(action: str, transaction_id: str | None = None, message_id: str | None = None,
            bpp_id: str | None = None, bpp_uri: str | None = None, city: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "domain": settings.domain,
        "action": action,
        "version": settings.version,
        "bap_id": settings.subscriber_id,
        "bap_uri": settings.subscriber_uri,
        "transaction_id": transaction_id or str(uuid4()),
        "message_id": message_id or str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "ttl": "PT30S",
        "location": {"country": {"code": settings.country}, "city": {"code": city or settings.default_city}},
    }
    if bpp_id:
        result["bpp_id"] = bpp_id
    if bpp_uri:
        result["bpp_uri"] = bpp_uri
    return result


def search_payload(*, start_gps: str, end_gps: str, city: str | None = None,
                   transaction_id: str | None = None, message_id: str | None = None) -> dict[str, Any]:
    if not start_gps or not end_gps:
        raise ValueError("start_gps and end_gps are required")
    return {
        "context": context("search", transaction_id, message_id, city=city),
        "message": {
            "intent": {
                "fulfillment": {
                    "stops": [
                        {"type": "START", "location": {"gps": start_gps}},
                        {"type": "END", "location": {"gps": end_gps}},
                    ],
                },
                "payment": {"collected_by": "BAP", "tags": [
                    {"descriptor": {"code": "BUYER_FINDER_FEES"}, "display": False, "list": [
                        {"descriptor": {"code": "BUYER_FINDER_FEES_PERCENTAGE"}, "value": settings.finder_fee_percentage}
                    ]},
                    {"descriptor": {"code": "SETTLEMENT_TERMS"}, "display": False, "list": [
                        {"descriptor": {"code": "SETTLEMENT_WINDOW"}, "value": "PT1D"},
                        {"descriptor": {"code": "SETTLEMENT_BASIS"}, "value": "DELIVERY"},
                        {"descriptor": {"code": "STATIC_TERMS"}, "value": settings.static_terms_url},
                    ]},
                ]},
            }
        },
    }


def action_payload(action: str, *, transaction_id: str, bpp_id: str, bpp_uri: str,
                   message: dict[str, Any], city: str | None = None) -> dict[str, Any]:
    if action not in {"select", "init", "confirm", "status", "cancel", "track", "update", "support", "issue"}:
        raise ValueError(f"Unsupported TRV10 action: {action}")
    return {"context": context(action, transaction_id, str(uuid4()), bpp_id, bpp_uri, city), "message": message}
