import json
from app.ondc.bpp.services.confirm import _enrich_fulfillment, bpp_confirm_service

# Test enrichment on a raw fulfillment from Pramaan
raw_fulfillment = {
    "id": "F1",
    "type": "Delivery",
    "tracking": False,
    "end": {
        "location": {
            "gps": "12.9715987,77.5945627",
            "address": {"area_code": "560001"}
        },
        "contact": {"phone": "9876543210"}
    }
}

enriched = _enrich_fulfillment(raw_fulfillment, "Packed")

print("=== ENRICHED FULFILLMENT PAYLOAD ===")
print(json.dumps(enriched, indent=2))

# Verify all mandatory RET10 fields
assert enriched.get("@ondc/org/provider_name") == "FromNear Store"
assert enriched["start"]["location"]["id"] == "L1"
assert enriched["start"]["location"]["descriptor"]["name"] == "FromNear Main Branch"
assert enriched["start"]["location"]["gps"] == "12.9715987,77.5945627"
assert enriched["start"]["location"]["address"]["locality"] == "M.G. Road"
assert enriched["start"]["location"]["address"]["city"] == "Bengaluru"
assert enriched["start"]["location"]["address"]["area_code"] == "560001"
assert enriched["start"]["location"]["address"]["state"] == "Karnataka"
assert enriched["start"]["contact"]["phone"] == "9876543210"
assert enriched["start"]["contact"]["email"] == "support@fromnear.com"

print("\n✅ ALL RET10 MANDATORY FULFILLMENT FIELDS VALIDATED!")
