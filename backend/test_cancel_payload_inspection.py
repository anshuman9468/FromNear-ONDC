import json
from app.ondc.bpp.order_builder import build_canonical_order, validate_ret10_payload, RET10_FULFILLMENT_STATE, _now

cancel_incoming_payload = {
    "context": {
        "domain": "ONDC:RET10",
        "country": "IND",
        "city": "std:080",
        "action": "cancel",
        "core_version": "1.2.0",
        "bap_id": "workbench.ondc.tech",
        "bap_uri": "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/buyer",
        "bpp_id": "ondc.fromnear.com",
        "bpp_uri": "https://ondc.fromnear.com/api/v1/ondc",
        "transaction_id": "48813e2f-8767-4899-b957-767d808e34e8",
        "message_id": "037b6559-25b3-47c1-ad17-88eafef42df7",
        "timestamp": _now(),
        "ttl": "PT30S"
    },
    "message": {
        "order_id": "2026-07-27-1001",
        "cancellation_reason_id": "001"
    }
}

created_at = _now()
updated_at = _now()

order_obj = build_canonical_order(
    action="on_cancel",
    payload=cancel_incoming_payload,
    state_code=RET10_FULFILLMENT_STATE["CANCELLED"],
    order_id="2026-07-27-1001",
    created_at=created_at,
    updated_at=updated_at,
)

print("=== GENERATED CANONICAL ORDER OBJECT FOR ON_CANCEL ===")
print(json.dumps(order_obj, indent=2))

out_payload = {
    "context": cancel_incoming_payload["context"],
    "message": {"order": order_obj}
}

errors = validate_ret10_payload("on_cancel", out_payload)
print("\n=== VALIDATION ERRORS ===")
print(errors)
