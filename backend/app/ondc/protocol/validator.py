import re
import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

logger = logging.getLogger("ondc.validator")

# RFC3339 Timestamp Regex (e.g. 2026-08-03T10:30:43.940Z)
TIMESTAMP_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z$")
TTL_REGEX = re.compile(r"^PT\d+[SMH]$")

ALLOWED_ACTIONS = {
    "search", "select", "init", "confirm", "status", "track", "cancel", "update", "support", "issue", "rating",
    "on_search", "on_select", "on_init", "on_confirm", "on_status", "on_track", "on_cancel", "on_update", "on_support", "on_issue", "on_rating"
}

class ONDCValidator:
    @staticmethod
    def validate(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validates the given ONDC payload against the v1.2.5 spec rules.
        Attempts to raise detailed warnings/errors for schema mismatch.
        """
        errors = []
        if not isinstance(payload, dict):
            return False, ["Payload must be a dictionary"]

        context = payload.get("context")
        message = payload.get("message")

        # 1. Context validation
        if not context or not isinstance(context, dict):
            errors.append("Missing context dictionary")
        else:
            # Domain
            domain = context.get("domain")
            if not domain or not isinstance(domain, str) or not domain.startswith("ONDC:"):
                errors.append(f"Invalid or missing domain: {domain}")
            
            # Action
            action = context.get("action")
            if action not in ALLOWED_ACTIONS:
                errors.append(f"Invalid action: {action}")
            
            # Country & City
            country = context.get("country")
            if not country or not isinstance(country, str) or len(country) != 3:
                errors.append(f"Invalid country (must be 3 letter ISO): {country}")
            
            city = context.get("city")
            if not city or not isinstance(city, str):
                errors.append(f"Invalid city format: {city}")

            # Version
            core_version = context.get("core_version")
            if core_version not in ["1.2.0", "1.2.5"]:
                errors.append(f"Invalid core_version (must be 1.2.0 or 1.2.5): {core_version}")
            
            # BAP details
            bap_id = context.get("bap_id")
            bap_uri = context.get("bap_uri")
            if not bap_id or not bap_uri:
                errors.append("bap_id and bap_uri are mandatory in context")
            
            # IDs
            transaction_id = context.get("transaction_id")
            message_id = context.get("message_id")
            if not transaction_id or len(transaction_id) > 36:
                errors.append(f"Invalid transaction_id length: {transaction_id}")
            if not message_id or len(message_id) > 36:
                errors.append(f"Invalid message_id length: {message_id}")

            # Timestamp
            timestamp = context.get("timestamp")
            if not timestamp or not isinstance(timestamp, str) or not TIMESTAMP_REGEX.match(timestamp):
                errors.append(f"Timestamp {timestamp} must be in RFC3339 UTC format (e.g. YYYY-MM-DDTHH:MM:SS.SSSZ)")
            
            # TTL
            ttl = context.get("ttl")
            if not ttl or not isinstance(ttl, str) or not TTL_REGEX.match(ttl):
                errors.append(f"TTL {ttl} must be ISO 8601 duration format (e.g. PT30S)")

        # 2. Message level validation
        if not message or not isinstance(message, dict):
            errors.append("Missing message dictionary")
        else:
            action = context.get("action") if context else ""

            # Validate cancellation reason code if action is cancel or on_cancel
            if action in ["cancel", "on_cancel"]:
                cancellation_reason_id = None
                if action == "cancel":
                    cancellation_reason_id = message.get("cancellation_reason_id")
                else:
                    order_obj = message.get("order") or {}
                    cancellation_reason_id = order_obj.get("cancellation", {}).get("reason", {}).get("id")
                
                allowed_reasons = {"001", "002", "003", "004", "005", "006", "007", "008", "009", "010", "011", "012", "013", "014", "015", "016", "017", "018", "019", "020", "021", "022", "023", "024", "025"}
                if cancellation_reason_id and cancellation_reason_id not in allowed_reasons:
                    errors.append(f"Invalid cancellation_reason_id: {cancellation_reason_id}. Allowed reasons: {sorted(list(allowed_reasons))}")
            
            # order / intent validation based on action
            if action in ["select", "init", "confirm", "status", "track", "cancel", "update", "issue"]:
                order_key = "issue" if action == "issue" else "order"
                obj = message.get(order_key)
                if not obj or not isinstance(obj, dict):
                    errors.append(f"Message must contain '{order_key}' dictionary for action {action}")
                else:
                    # Validate tags inside order/intent if present
                    tags = obj.get("tags")
                    if tags is not None:
                        if not isinstance(tags, list):
                            errors.append("tags must be an array (list)")
                        else:
                            for idx, t in enumerate(tags):
                                if not isinstance(t, dict) or "code" not in t or "list" not in t:
                                    errors.append(f"Tag at index {idx} must contain 'code' and 'list'")
                                elif not isinstance(t.get("list"), list):
                                    errors.append(f"Tag list at index {idx} must be an array")
                                else:
                                    for item in t["list"]:
                                        if not isinstance(item, dict) or "code" not in item or "value" not in item:
                                            errors.append(f"Tag item in {t['code']} must contain 'code' and 'value'")

                    # Validate items
                    items = obj.get("items")
                    if items is not None:
                        if not isinstance(items, list):
                            errors.append("items must be an array (list)")
                        else:
                            for idx, it in enumerate(items):
                                if not isinstance(it, dict) or "id" not in it:
                                    errors.append(f"Item at index {idx} must contain 'id'")
                                if "parent_item_id" in it and not isinstance(it["parent_item_id"], str):
                                    errors.append(f"Item parent_item_id at index {idx} must be a string")
                                if "tags" in it and not isinstance(it["tags"], list):
                                    errors.append(f"Item tags at index {idx} must be an array")

                    # Validate fulfillments
                    fulfillments = obj.get("fulfillments")
                    if fulfillments is not None:
                        if not isinstance(fulfillments, list):
                            errors.append("fulfillments must be an array (list)")
                        else:
                            for idx, f in enumerate(fulfillments):
                                if "tags" in f and not isinstance(f["tags"], list):
                                    errors.append(f"Fulfillment tags at index {idx} must be an array")

                    # Validate payment
                    payment = obj.get("payment")
                    if payment is not None:
                        if not isinstance(payment, dict):
                            errors.append("payment must be a dictionary")
                        else:
                            settlement_details = payment.get("@ondc/org/settlement_details")
                            if settlement_details is not None and not isinstance(settlement_details, list):
                                errors.append("@ondc/org/settlement_details must be an array")

                    # Validate quote
                    quote = obj.get("quote")
                    if quote is not None:
                        if not isinstance(quote, dict):
                            errors.append("quote must be a dictionary")
                        else:
                            breakup = quote.get("breakup")
                            if breakup is not None:
                                if not isinstance(breakup, list):
                                    errors.append("quote breakup must be an array")
                                else:
                                    for entry in breakup:
                                        if not isinstance(entry, dict):
                                            errors.append("quote breakup entry must be a dictionary")
                                            continue
                                        title_type = entry.get("@ondc/org/title_type")
                                        if title_type == "item" and "item" not in entry:
                                            errors.append("quote breakup item entry must contain nested 'item' object")

        if errors:
            logger.warning(f"ONDC Protocol Validation Warnings/Errors: {errors}")
            return False, errors

        return True, []
