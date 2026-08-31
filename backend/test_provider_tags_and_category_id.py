import re
from app.ondc.bpp.services.search import (
    bpp_search_service,
    ALLOWED_PROVIDER_TAG_CODES,
    CATEGORY_ID_REGEX,
    OFFICIAL_RET10_GROCERY_CATEGORIES,
)

cat = bpp_search_service.mock_catalog

print("=== STARTING PROVIDER TAGS AND CATEGORY ID AUDIT ===")

# 1. Check Descriptor Tags (bpp_terms must be here)
desc_tags = cat.get("bpp/descriptor", {}).get("tags", [])
bpp_terms_desc = [t for t in desc_tags if t.get("code") == "bpp_terms"]
assert bpp_terms_desc, "bpp/descriptor.tags missing bpp_terms!"
print("✅ bpp_terms tag found in bpp/descriptor.tags!")

# 2. Check Provider Tags (bpp_terms MUST NOT be here; only ALLOWED_PROVIDER_TAG_CODES allowed)
for provider in cat.get("bpp/providers", []):
    prov_tags = provider.get("tags", [])
    for tag in prov_tags:
        code = tag.get("code")
        assert code in ALLOWED_PROVIDER_TAG_CODES, f"Invalid provider tag code '{code}' under provider! Allowed: {ALLOWED_PROVIDER_TAG_CODES}"
    print("✅ Provider tags validated! No invalid tag codes found under provider.tags!")

    # 3. Check Categories ID (regex ^[a-zA-Z0-9]{1,12}$)
    categories = provider.get("categories", [])
    for category in categories:
        cat_id = category.get("id")
        assert CATEGORY_ID_REGEX.match(cat_id), f"Category ID '{cat_id}' does not match regex ^[a-zA-Z0-9]{{1,12}}$!"
        print(f"✅ Category ID '{cat_id}' matches regex ^[a-zA-Z0-9]{{1,12}}$!")

    # RET10 item category_id is the published grocery category enum (for
    # example, "Rice and Rice Products"). The short alphanumeric constraint
    # applies to provider category object IDs, not this item enum.
    for item in provider.get("items", []):
        item_id = item.get("id")
        item_cat_id = item.get("category_id")
        assert item_cat_id in OFFICIAL_RET10_GROCERY_CATEGORIES, (
            f"Item {item_id} category_id '{item_cat_id}' is not a RET10 grocery category"
        )
        print(f"✅ Item {item_id} category_id '{item_cat_id}' is a RET10 grocery category!")

print("\n🎉 ALL PROVIDER TAGS AND CATEGORY ID CHECKS PASSED WITH 0 ERRORS!")
