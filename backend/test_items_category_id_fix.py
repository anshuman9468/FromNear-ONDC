from app.ondc.bpp.services.search import bpp_search_service, OFFICIAL_RET10_GROCERY_CATEGORIES, CATEGORY_ID_REGEX

cat = bpp_search_service.mock_catalog

print("=== STARTING ITEMS_CATEGORY_ID VALIDATION AUDIT ===")

for provider in cat.get("bpp/providers", []):
    for category in provider.get("categories", []):
        cat_id = category.get("id")
        assert CATEGORY_ID_REGEX.match(cat_id), f"Provider category id '{cat_id}' invalid!"
        print(f"✅ Provider category id: '{cat_id}' (matches ^[a-zA-Z0-9]{{1,12}}$)")

    for item in provider.get("items", []):
        item_id = item.get("id")
        item_cat_id = item.get("category_id")
        assert item_cat_id in OFFICIAL_RET10_GROCERY_CATEGORIES, f"Item {item_id} category_id '{item_cat_id}' is NOT an official RET10 category!"
        print(f"✅ Item {item_id} category_id: '{item_cat_id}' (is official RET10 grocery category)")

print("\n🎉 ITEMS_CATEGORY_ID AND PROVIDER CATEGORY ID AUDIT PASSED WITH 0 ERRORS!")
