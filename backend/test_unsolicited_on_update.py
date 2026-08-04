import asyncio
from app.ondc.bpp.order_builder import build_canonical_order, validate_ret10_payload, _now, RET10_FULFILLMENT_STATE

ctx = {
    "domain": "ONDC:RET10",
    "country": "IND",
    "city": "std:080",
    "action": "confirm",
    "core_version": "1.2.0",
    "bap_id": "workbench.ondc.tech",
    "bap_uri": "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/buyer",
    "bpp_id": "ondc.fromnear.com",
    "bpp_uri": "https://ondc.fromnear.com/api/v1/ondc",
    "transaction_id": "48813e2f-8767-4899-b957-767d808e34e8",
    "message_id": "037b6559-25b3-47c1-ad17-88eafef42df7",
    "timestamp": _now(),
    "ttl": "PT30S"
}

payload = {
    "context": ctx,
    "message": {
        "order": {
            "id": "2026-07-27-1001",
            "provider": {"id": "P1", "locations": [{"id": "L1"}]},
            "items": [{"id": "I1", "quantity": {"count": 1}}],
            "billing": {
                "name": "John Doe",
                "phone": "9876543210",
                "address": {"door": "123", "street": "MG Road", "city": "Bengaluru", "state": "Karnataka", "area_code": "560001"}
            },
            "fulfillments": [
                {
                    "id": "F1",
                    "type": "Delivery",
                    "end": {
                        "location": {"gps": "12.9715987,77.5945627", "address": {"area_code": "560001"}},
                        "contact": {"phone": "9876543210"}
                    }
                }
            ]
        }
    }
}

print("=== TESTING UNSOLICITED ON_UPDATE PAYLOAD SCHEMA ===")

# Step 1: on_confirm
confirm_obj = build_canonical_order("on_confirm", payload, RET10_FULFILLMENT_STATE["PACKED"], "2026-07-27-1001")
confirm_payload = {"context": ctx, "message": {"order": confirm_obj}}
err1 = validate_ret10_payload("on_confirm", confirm_payload)
assert not err1, f"on_confirm failed: {err1}"
print("✅ Step 6: on_confirm payload validated with 0 errors!")

# Step 2: unsolicited on_update (Step 7 in Pramaan)
update_obj = build_canonical_order("on_update", payload, "Packed", "2026-07-27-1001")
update_obj["state"] = "In-progress"
update_payload = {"context": ctx, "message": {"order": update_obj}}
err2 = validate_ret10_payload("on_update", update_payload)
assert not err2, f"on_update failed: {err2}"
print("✅ Step 7: unsolicited on_update payload validated with 0 errors!")

print("\n🎉 UNSOLICITED ON_UPDATE VALIDATION AUDIT PASSED WITH 0 ERRORS!")
