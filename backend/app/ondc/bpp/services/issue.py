import asyncio
import copy
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.settings import settings
from app.ondc.bpp.client import bpp_client

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _participant(domain: str) -> Dict[str, Any]:
    return {
        "org": {"name": f"{settings.ONDC_SUBSCRIBER_ID}::{domain}"},
        "contact": {"phone": "9876543210", "email": "support@fromnear.com"},
        "person": {"name": "FromNear Support"},
    }


def _normalize_issue(payload: Dict[str, Any], status_value: str, action_value: str, short_desc: str) -> Dict[str, Any]:
    context = payload.get("context", {})
    domain = context.get("domain") or settings.ONDC_DOMAIN
    timestamp = _now()
    issue = copy.deepcopy(payload.get("message", {}).get("issue", {}))

    issue.setdefault("id", context.get("message_id", "ISSUE-001"))
    issue.setdefault("category", "ITEM")
    issue.setdefault("sub_category", "ITM01")
    issue["bap_id"] = issue.get("bap_id") or context.get("bap_id", "workbench.ondc.tech")
    issue["bpp_id"] = issue.get("bpp_id") or settings.ONDC_SUBSCRIBER_ID
    issue["status"] = status_value
    issue.setdefault("issue_type", "ISSUE")
    issue.setdefault("created_at", timestamp)
    issue["updated_at"] = timestamp
    issue.setdefault("expected_response_time", {"duration": "PT2H"})
    issue.setdefault("expected_resolution_time", {"duration": "P1D"})

    issue.setdefault(
        "complainant_info",
        {
            "person": {"name": "Jane Doe"},
            "contact": {"phone": "9876543210", "email": "buyer@example.com"},
        },
    )
    issue.setdefault(
        "description",
        {
            "short_desc": "Issue with item",
            "long_desc": "Issue reported for the order",
            "additional_desc": {
                "url": "https://ondc.fromnear.com/proof.jpg",
                "content_type": "text/plain",
            },
            "images": ["https://ondc.fromnear.com/proof.jpg"],
        },
    )
    issue.setdefault(
        "source",
        {
            "network_participant_id": context.get("bap_id", "workbench.ondc.tech"),
            "type": "CONSUMER",
        },
    )
    issue.setdefault(
        "order_details",
        {
            "id": "2026-07-27-1001",
            "state": "Completed",
            "items": [{"id": "I1", "quantity": 1}],
            "fulfillments": [{"id": "F1", "state": "Order-delivered"}],
            "provider_id": "P1",
        },
    )
    issue["resolution_provider"] = {
        "respondent_info": {
            "type": "TRANSACTION-COUNTERPARTY-NP",
            "organization": {
                "org": {"name": f"{settings.ONDC_SUBSCRIBER_ID}::{domain}"},
                "contact": {"phone": "9876543210", "email": "support@fromnear.com"},
                "person": {"name": "FromNear Support"},
            },
            "resolution_support": {
                "chat_link": "https://ondc.fromnear.com/support/chat",
                "contact": {"phone": "9876543210", "email": "support@fromnear.com"},
                "gros": [
                    {
                        "person": {"name": "FromNear Grievance Officer"},
                        "contact": {"phone": "9876543210", "email": "grievance@fromnear.com"},
                        "gro_type": "TRANSACTION-COUNTERPARTY-NP-GRO",
                    }
                ],
            },
        }
    }

    issue_actions = issue.setdefault("issue_actions", {})
    issue_actions.setdefault("complainant_actions", [])
    respondent_actions = issue_actions.setdefault("respondent_actions", [])
    respondent_actions.append(
        {
            "respondent_action": action_value,
            "short_desc": short_desc,
            "updated_at": timestamp,
            "updated_by": _participant(domain),
        }
    )
    return issue


class BppIssueService:
    async def process_issue(self, payload: Dict[str, Any]) -> None:
        context = payload.get("context", {})

        await asyncio.sleep(0.5)
        processing_issue = _normalize_issue(
            payload=payload,
            status_value="PROCESSING",
            action_value="PROCESSING",
            short_desc="Seller has acknowledged the issue",
        )
        await bpp_client.send_callback(context, "on_issue", {"issue": processing_issue})

        await asyncio.sleep(0.7)
        resolved_issue = _normalize_issue(
            payload=payload,
            status_value="RESOLVED",
            action_value="RESOLVED",
            short_desc="Seller has resolved the issue",
        )
        await bpp_client.send_unsolicited(context, "on_issue_status", {"issue": resolved_issue})

    async def handle_issue(self, payload: Dict[str, Any]) -> None:
        await self.process_issue(payload)
        logger.info("Accepted /issue for tx %s", payload.get("context", {}).get("transaction_id"))


bpp_issue_service = BppIssueService()
