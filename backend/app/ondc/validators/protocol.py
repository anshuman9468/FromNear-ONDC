import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from fastapi import Request
from app.ondc.crypto.utils import verify_auth_header
from app.ondc.registry.client import registry_client

logger = logging.getLogger(__name__)


def parse_iso_datetime(dt_str: str) -> Optional[datetime]:
    """Parse ISO 8601 string into a timezone-aware datetime."""
    # Replace 'Z' with UTC offset '+00:00' to handle standard format
    cleaned_str = dt_str.replace("Z", "+00:00")
    try:
        # Standard formats
        return datetime.fromisoformat(cleaned_str)
    except ValueError:
        # Support milliseconds, fallback parsing
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z"):
            try:
                return datetime.strptime(cleaned_str, fmt)
            except ValueError:
                continue
    return None


def validate_timestamp(timestamp_str: str, max_skew_seconds: int = 300) -> Tuple[bool, str]:
    """Validate that ONDC context timestamp is within acceptable time skew."""
    dt = parse_iso_datetime(timestamp_str)
    if not dt:
        return False, "Invalid context timestamp format"
        
    now = datetime.now(timezone.utc)
    # Ensure dt has timezone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
        
    difference = abs((now - dt).total_seconds())
    if difference > max_skew_seconds:
        return False, f"Timestamp is outside acceptable skew window. Skew: {difference:.1f}s"
        
    return True, ""


async def validate_ondc_signature(
    request: Request,
    body: bytes,
    context: Dict[str, Any]
) -> Tuple[bool, str]:
    """Validate ONDC request signature against sender public key looked up from Registry."""
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if not auth_header:
        return False, "Missing Authorization header"

    action = context.get("action")
    
    # Identify sender:
    # If action is callback (e.g. on_search), the sender is BPP (Provider).
    # If action is command (e.g. search), the sender is BAP (Buyer).
    # The BAP registry public key will be looked up if BAP is receiving callbacks, etc.
    sender_id = None
    if action and action.startswith("on_"):
        sender_id = context.get("bpp_id")
    else:
        sender_id = context.get("bap_id")
        
    if not sender_id:
        return False, f"Missing sender identifier for action '{action}'"
        
    # Get unique key ID (sometimes sent in context, or parsed from signature header)
    # Format of ONDC Signature header: Signature keyId="subscriber_id|ukid|ed25519"
    # We parse the ukid from keyId header field.
    try:
        from app.ondc.crypto.utils import parse_auth_header
        parsed_header = parse_auth_header(auth_header)
        key_id_parts = parsed_header.get("keyId", "").split("|")
        if len(key_id_parts) >= 2:
            unique_key_id = key_id_parts[1]
        else:
            unique_key_id = "default"
    except Exception:
        unique_key_id = "default"
        
    # Look up the public key from the ONDC Registry
    public_key = await registry_client.get_signing_public_key(
        subscriber_id=sender_id, unique_key_id=unique_key_id
    )
    
    if not public_key:
        return False, f"Sender public key not found in registry: {sender_id} (keyId: {unique_key_id})"
        
    # Verify the signature
    is_valid = verify_auth_header(header=auth_header, body=body, public_key_str=public_key)
    if not is_valid:
        return False, "Signature verification failed"
        
    return True, ""
