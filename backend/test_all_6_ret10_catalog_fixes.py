import json
from app.ondc.bpp.services.search import bpp_search_service, OFFICIAL_RET10_GROCERY_CATEGORIES, ALLOWED_UNITS

cat = bpp_search_service.mock_catalog

print("=== STARTING RET10 1.2.0 CATALOG VALIDATION AUDIT (ALL 6 POINTS) ===")

# 1. TAGS_BPP_TERMS_NP_TYPE
desc_tags = cat.get("bpp/descriptor", {}).get("tags", [])
bpp_terms_desc = [t for t in desc_tags if t.get("code") == "bpp_terms"]
assert bpp_terms_desc, "1. TAGS_BPP_TERMS_NP_TYPE: bpp/descriptor.tags missing bpp_terms!"
np_type = bpp_terms_desc[0].get("list", [{}])[0].get("value")
assert np_type == "MSN", f"1. TAGS_BPP_TERMS_NP_TYPE: np_type must be MSN, got {np_type}"
print("✅ 1. TAGS_BPP_TERMS_NP_TYPE: bpp_terms tag with np_type 'MSN' verified!")

for provider in cat.get("bpp/providers", []):
    prov_tags = provider.get("tags", [])
    # RET10 places the MSN type under bpp/descriptor.tags. Provider tags have
    # their own restricted vocabulary and must not repeat bpp_terms.
    assert all(t.get("code") != "bpp_terms" for t in prov_tags), (
        "1. TAGS_BPP_TERMS_NP_TYPE: bpp_terms belongs under bpp/descriptor.tags"
    )

    for item in provider.get("items", []):
        item_id = item.get("id")

        # 2 & 3. ITEMS_TIME_LABEL & ITEMS_TIME_TIMESTAMP
        item_time = item.get("time", {})
        assert item_time.get("label") in ("enable", "disable"), f"2. ITEMS_TIME_LABEL: item {item_id} label invalid"
        assert item_time.get("timestamp"), f"3. ITEMS_TIME_TIMESTAMP: item {item_id} timestamp missing"
        print(f"✅ 2&3. ITEMS_TIME: item {item_id} time ({item_time['label']}, {item_time['timestamp']}) verified!")

        # 4. ITEMS_QUANTITY_UNITIZED_MEASURE_UNIT
        unit = item.get("quantity", {}).get("unitized", {}).get("measure", {}).get("unit")
        assert unit in ALLOWED_UNITS, f"4. ITEMS_QUANTITY_UNITIZED_MEASURE_UNIT: item {item_id} unit '{unit}' not in ALLOWED_UNITS!"
        print(f"✅ 4. ITEMS_QUANTITY_UNITIZED_MEASURE_UNIT: item {item_id} unit '{unit}' verified!")

        # 5. ITEMS_QUANTITY_AVAILABLE_COUNT
        avail_count = item.get("quantity", {}).get("available", {}).get("count")
        assert isinstance(avail_count, str), f"5. ITEMS_QUANTITY_AVAILABLE_COUNT: item {item_id} count is not string"
        print(f"✅ 5. ITEMS_QUANTITY_AVAILABLE_COUNT: item {item_id} count '{avail_count}' (string) verified!")

        # 6. ITEMS_CATEGORY_ID
        category_id = item.get("category_id")
        assert category_id in OFFICIAL_RET10_GROCERY_CATEGORIES, f"6. ITEMS_CATEGORY_ID: item {item_id} category '{category_id}' invalid"
        print(f"✅ 6. ITEMS_CATEGORY_ID: item {item_id} category_id '{category_id}' verified!")

print("\n🎉 ALL 6 RET10 1.2.0 DISCOVERY CATALOG SCHEMAS FULLY VALIDATED WITH 0 ERRORS!")
