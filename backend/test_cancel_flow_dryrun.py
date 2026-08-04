import json
import logging
from app.ondc.bpp.order_builder import build_canonical_order, validate_ret10_payload, RET10_FULFILLMENT_STATE, _now
from app.core.settings import settings

logging.basicConfig(level=logging.INFO)

base_context = {
    "domain": "ONDC:RET10",
    "country": "IND",
    "city": "std:080",
    "action": "cancel",
    "core_version": "1.2.0",
    "bap_id": "workbench.ondc.tech",
    "bap_uri": "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/buyer",
    "bpp_id": settings.ONDC_SUBSCRIBER_ID,
    "bpp_uri": settings.ONDC_SUBSCRIBER_URI,
    "transaction_id": "48813e2f-8767-4899-b957-767d808e34e8",
    "message_id": "037b6559-25b3-47c1-ad17-88eafef42df7",
    "timestamp": _now(),
    "ttl": "PT30S"
}

sample_cancel_payload = {
    "context": base_context,
    "message": {
        "order_id": "2026-07-27-1001",
        "cancellation_reason_id": "001"
    }
}

print("=== STARTING BUYER CANCELLATION FLOW DRY-RUN AUDIT ===")

created_at = _now()
updated_at = _now()

order_obj = build_canonical_order(
    action="on_cancel",
    payload=sample_cancel_payload,
    state_code=RET10_FULFILLMENT_STATE["CANCELLED"],
    order_id="2026-07-27-1001",
    created_at=created_at,
    updated_at=updated_at,
)
order_obj["state"] = "Cancelled"
order_obj["cancellation"] = {
    "cancelled_by": base_context["bap_id"],
    "reason": {"id": "001"}
}

out_payload = {
    "context": base_context,
    "message": {"order": order_obj}
}

errors = validate_ret10_payload("on_cancel", out_payload)
if errors:
    print("❌ BUYER CANCELLATION ON_CANCEL FAILED VALIDATION:")
    for err in errors:
        print(f"   - {err}")
else:
    print("✅ BUYER CANCELLATION ON_CANCEL PASSED RET10 1.2.0 VALIDATION!")
