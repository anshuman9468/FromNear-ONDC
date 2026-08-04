import json
import logging
from app.ondc.bpp.order_builder import build_canonical_order, validate_ret10_payload, RET10_FULFILLMENT_STATE, _now
from app.core.settings import settings

logging.basicConfig(level=logging.INFO)

base_context = {
    "domain": "ONDC:RET10",
    "country": "IND",
    "city": "std:080",
    "action": "search",
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

sample_payload = {
    "context": base_context,
    "message": {
        "order": {
            "id": "2026-07-27-1001",
            "provider": {"id": "P1", "locations": [{"id": "L1"}]},
            "items": [
                {"id": "I1", "quantity": {"count": 1}},
                {"id": "I2", "quantity": {"count": 1}}
            ],
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

actions = [
    ("on_select", "Serviceable"),
    ("on_init", "Serviceable"),
    ("on_confirm", RET10_FULFILLMENT_STATE["PACKED"]),
    ("on_status", RET10_FULFILLMENT_STATE["AGENT_ASSIGNED"]),
    ("on_status", RET10_FULFILLMENT_STATE["PICKED_UP"]),
    ("on_status", RET10_FULFILLMENT_STATE["OUT_FOR_DELIVERY"]),
    ("on_status", RET10_FULFILLMENT_STATE["DELIVERED"]),
    ("on_status", RET10_FULFILLMENT_STATE["DELIVERED"]),
    ("on_status", RET10_FULFILLMENT_STATE["DELIVERED"]),
    ("on_update", "Return-Initiated"),
    ("on_update", "Return-Picked"),
    ("on_update", "Return-Delivered"),
]

print("=== STARTING FULL RET10 1.2.0 LIFECYCLE DRY-RUN AUDIT ===")

all_passed = True
created_at = _now()

for idx, (action, state_code) in enumerate(actions, start=1):
    ctx = base_context.copy()
    ctx["action"] = action
    ctx["timestamp"] = _now()
    step_payload = {"context": ctx, "message": sample_payload["message"]}

    updated_at = _now()
    order_obj = build_canonical_order(
        action=action,
        payload=step_payload,
        state_code=state_code,
        order_id="2026-07-27-1001",
        created_at=created_at,
        updated_at=updated_at,
    )

    out_payload = {
        "context": ctx,
        "message": {"order": order_obj}
    }

    errors = validate_ret10_payload(action, out_payload)
    if errors:
        all_passed = False
        print(f"❌ STEP {idx} [{action} - {state_code}] FAILED VALIDATION:")
        for err in errors:
            print(f"   - {err}")
    else:
        print(f"✅ STEP {idx} [{action} - {state_code}] PASSED RET10 VALIDATION!")

if all_passed:
    print("\n🎉 ALL 12 CALLBACK LIFE-CYCLE PAYLOADS PASSED RET10 1.2.0 VALIDATION WITH 0 ERRORS!")
else:
    print("\n❌ SOME LIFE-CYCLE PAYLOADS FAILED RET10 VALIDATION.")
