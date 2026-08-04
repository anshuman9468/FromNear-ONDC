import json
import logging
import asyncio
import copy
import re
from pathlib import Path
from app.ondc.bpp.client import bpp_client
from app.ondc.bpp.order_builder import _now

logger = logging.getLogger(__name__)

ALLOWED_PROVIDER_TAG_CODES = {"timing", "close_timing", "serviceability", "order_value", "np_fees", "FSSAI", "bpp_terms"}
CATEGORY_ID_REGEX = re.compile(r"^[a-zA-Z0-9]{1,12}$")
ALLOWED_UNITS = {"unit", "dozen", "gram", "kilogram", "tonne", "litre", "millilitre"}

OFFICIAL_RET10_GROCERY_CATEGORIES = {
    "Fruits and Vegetables", "Masala & Seasoning", "Oil & Ghee", "Eggs, Meat & Fish",
    "Cleaning & Household", "Bakery, Cakes & Dairy", "Pet Care", "Stationery",
    "Detergents and Dishwash", "Dairy and Cheese", "Snacks, Dry Fruits, Nuts",
    "Pasta, Soup and Noodles", "Cereals and Breakfast", "Sauces, Spreads and Dips",
    "Chocolates and Biscuits", "Cooking and Baking Needs", "Tinned and Processed Food",
    "Atta, Flours and Sooji", "Rice and Rice Products", "Dals and Pulses",
    "Salt, Sugar and Jaggery", "Energy and Soft Drinks", "Water", "Tea and Coffee",
    "Fruit Juices and Fruit Drinks", "Snacks and Namkeen", "Ready to Cook and Eat",
    "Pickles and Chutney", "Indian Sweets", "Frozen Vegetables", "Frozen Snacks", "Gift Voucher"
}


def _normalize_catalog_quantities(catalog: dict) -> dict:
    """Ensure provider tags and category IDs conform 100% to RET10 validator rules."""
    cat = copy.deepcopy(catalog)
    now_ts = _now()

    # 1. Descriptor Tags (bpp_terms placed exclusively here)
    desc = cat.get("bpp/descriptor", {})
    desc_tags = desc.get("tags", [])
    if not any(t.get("code") == "bpp_terms" for t in desc_tags):
        desc_tags.append({
            "code": "bpp_terms",
            "list": [{"code": "np_type", "value": "MSN"}]
        })
    desc["tags"] = desc_tags
    cat["bpp/descriptor"] = desc

    for provider in cat.get("bpp/providers", []):
        provider["ttl"] = provider.get("ttl", "PT24H")
        provider["status"] = "active"
        provider["@ondc/org/provider_status"] = "active"
        if "time" not in provider:
            provider["time"] = {}
        provider["time"]["label"] = provider["time"].get("label", "enable")
        provider["time"]["timestamp"] = now_ts

        # 2. Filter provider tags to ONLY allowed provider tag codes
        p_tags = provider.get("tags", [])
        # Add FSSAI tag if missing (mandatory for food/grocery providers in ONDC)
        if not any(t.get("code") == "FSSAI" for t in p_tags):
            p_tags.append({
                "code": "FSSAI",
                "list": [
                    {"code": "license_no", "value": "12345678901234"}
                ]
            })
        # Add bpp_terms tag if missing
        if not any(t.get("code") == "bpp_terms" for t in p_tags):
            p_tags.append({
                "code": "bpp_terms",
                "list": [{"code": "np_type", "value": "MSN"}]
            })
        filtered_p_tags = [t for t in p_tags if t.get("code") in ALLOWED_PROVIDER_TAG_CODES]
        provider["tags"] = filtered_p_tags

        for loc in provider.get("locations", []):
            if "time" not in loc:
                loc["time"] = {}
            loc["time"]["label"] = loc["time"].get("label", "enable")
            loc["time"]["timestamp"] = now_ts
            loc["time"]["days"] = ["1", "2", "3", "4", "5", "6", "7"]
            if "range" not in loc["time"]:
                loc["time"]["range"] = {"start": "0900", "end": "2100"}
            if "schedule" not in loc["time"]:
                loc["time"]["schedule"] = {"holidays": []}

        # 3. Provider Categories validation (categories[*].id regex ^[a-zA-Z0-9]{1,12}$)
        categories = provider.get("categories", [])
        for idx, category in enumerate(categories):
            cat_id = category.get("id", f"CAT00{idx+1}")
            if not CATEGORY_ID_REGEX.match(cat_id):
                category["id"] = f"CAT00{idx+1}"
        provider["categories"] = categories

        # 4. Item level validation (items[*].category_id must be an official RET10 grocery category string)
        for item in provider.get("items", []):
            item["time"] = {
                "label": "enable",
                "timestamp": now_ts
            }

            item_desc = item.get("descriptor", {})
            if "code" not in item_desc or not (item_desc["code"].startswith("1:") or item_desc["code"].startswith("5:")):
                item_desc["code"] = "1:1001"
            item["descriptor"] = item_desc

            # Retain official RET10 category name in items[*].category_id
            cat_id = item.get("category_id")
            if cat_id not in OFFICIAL_RET10_GROCERY_CATEGORIES:
                item["category_id"] = "Atta, Flours and Sooji"

            qty = item.get("quantity", {})
            if "available" in qty and "count" in qty["available"]:
                qty["available"]["count"] = str(qty["available"]["count"])
            else:
                qty["available"] = {"count": "99"}

            if "maximum" in qty and "count" in qty["maximum"]:
                qty["maximum"]["count"] = str(qty["maximum"]["count"])
            else:
                qty["maximum"] = {"count": "5"}

            unitized = qty.get("unitized", {})
            measure = unitized.get("measure", {})
            unit = measure.get("unit", "kilogram").lower()
            if unit not in ALLOWED_UNITS:
                unit = "kilogram" if unit in ("kg", "kgs", "kilo") else "unit"
            measure["unit"] = unit
            measure["value"] = str(measure.get("value", "1"))
            unitized["measure"] = measure
            qty["unitized"] = unitized
            item["quantity"] = qty

    return cat


class BppSearchService:
    def __init__(self):
        catalog_path = Path(__file__).parent.parent / "catalog" / "mock_catalog.json"
        with open(catalog_path, "r") as f:
            raw_catalog = json.load(f)
        self.mock_catalog = _normalize_catalog_quantities(raw_catalog)

    async def process_search(self, payload: dict):
        """Asynchronously process the incoming search request and send on_search."""
        context = payload.get("context", {})

        await asyncio.sleep(1)

        normalized_catalog = _normalize_catalog_quantities(self.mock_catalog)
        message = {
            "catalog": normalized_catalog
        }

        await bpp_client.send_callback(context, "on_search", message)

    async def handle_search(self, payload: dict):
        asyncio.create_task(self.process_search(payload))
        logger.info(f"Accepted /search request for transaction {payload.get('context', {}).get('transaction_id')}")


bpp_search_service = BppSearchService()
