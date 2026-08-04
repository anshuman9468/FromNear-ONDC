import json
from app.ondc.bpp.services.search import bpp_search_service, _normalize_catalog_quantities

cat = bpp_search_service.mock_catalog

print("=== CHECKING CATALOG ITEM QUANTITY TYPES ===")
for provider in cat.get("bpp/providers", []):
    for item in provider.get("items", []):
        item_id = item.get("id")
        qty = item.get("quantity", {})
        avail_count = qty.get("available", {}).get("count")
        max_count = qty.get("maximum", {}).get("count")

        print(f"Item {item_id}:")
        print(f"  available.count: {repr(avail_count)} (type: {type(avail_count).__name__})")
        print(f"  maximum.count: {repr(max_count)} (type: {type(max_count).__name__})")

        assert isinstance(avail_count, str), f"Item {item_id} available.count is not a string!"
        assert isinstance(max_count, str), f"Item {item_id} maximum.count is not a string!"

print("\n✅ ALL CATALOG ITEM QUANTITY COUNTS ARE STAGE 100% VALIDATED AS STRINGS!")
