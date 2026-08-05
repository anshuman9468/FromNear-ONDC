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
VALID_FULFILLMENT_TYPES = {"Delivery", "Self-Pickup"}
FSSAI_LICENSE_NO = "12345678901234"

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

DEFAULT_ITEM_TAGS = [
    {
        "code": "type",
        "list": [{"code": "type", "value": "item"}],
    }
]


def _stringify_statutory_fields(statutory: dict) -> dict:
    """Ensure all statutory_reqs_prepackaged_food values are non-empty strings."""
    if not statutory:
        return {}
    result = {}
    for key, value in statutory.items():
        result[key] = str(value) if value is not None else ""
    return result


def _build_catalog_fulfillments(providers: list) -> list:
    """Build top-level bpp/fulfillments array with only valid RET10 types."""
    fulfillments = []
    seen = set()
    for provider in providers:
        for f in provider.get("fulfillments", []):
            f_type = f.get("type", "Delivery")
            if f_type not in VALID_FULFILLMENT_TYPES:
                f_type = "Delivery"
            f_id = f.get("id", "F1")
            key = (f_id, f_type)
            if key in seen:
                continue
            seen.add(key)
            fulfillments.append({
                "id": f_id,
                "type": f_type,
                "contact": {
                    "phone": f.get("contact", {}).get("phone", "9876543210"),
                    "email": f.get("contact", {}).get("email", "support@fromnear.com"),
                },
            })
    if not fulfillments:
        fulfillments = [{
            "id": "F1",
            "type": "Delivery",
            "contact": {"phone": "9876543210", "email": "support@fromnear.com"},
        }]
    return fulfillments


def _normalize_catalog_quantities(catalog: dict) -> dict:
    """Ensure provider tags and category IDs conform 100% to RET10 validator rules."""
    cat = copy.deepcopy(catalog)
    now_ts = _now()

    desc = cat.get("bpp/descriptor", {})
    desc_tags = desc.get("tags", [])
    if not any(t.get("code") == "bpp_terms" for t in desc_tags):
        desc_tags.append({
            "code": "bpp_terms",
            "list": [{"code": "np_type", "value": "MSN"}],
        })
    desc["tags"] = desc_tags
    cat["bpp/descriptor"] = desc

    providers = cat.get("bpp/providers", [])
    for provider in providers:
        provider["ttl"] = provider.get("ttl", "PT24H")
        provider["status"] = "active"
        provider["@ondc/org/provider_status"] = "active"
        provider["@ondc/org/fssai_license_no"] = str(
            provider.get("@ondc/org/fssai_license_no") or FSSAI_LICENSE_NO
        )

        if "time" not in provider:
            provider["time"] = {}
        provider["time"]["label"] = provider["time"].get("label", "enable")
        provider["time"]["timestamp"] = now_ts

        p_tags = provider.get("tags", [])
        if not any(t.get("code") == "FSSAI" for t in p_tags):
            p_tags.append({
                "code": "FSSAI",
                "list": [{"code": "license_no", "value": FSSAI_LICENSE_NO}],
            })
        if not any(t.get("code") == "bpp_terms" for t in p_tags):
            p_tags.append({
                "code": "bpp_terms",
                "list": [{"code": "np_type", "value": "MSN"}],
            })
        provider["tags"] = [t for t in p_tags if t.get("code") in ALLOWED_PROVIDER_TAG_CODES]

        for loc in provider.get("locations", []):
            if "time" not in loc:
                loc["time"] = {}
            loc["time"]["label"] = loc["time"].get("label", "enable")
            loc["time"]["timestamp"] = now_ts
            if isinstance(loc["time"].get("days"), str):
                loc["time"]["days"] = loc["time"]["days"].split(",")
            else:
                loc["time"]["days"] = loc["time"].get("days") or ["1", "2", "3", "4", "5", "6", "7"]
            if "range" not in loc["time"]:
                loc["time"]["range"] = {"start": "0900", "end": "2100"}
            if "schedule" not in loc["time"]:
                loc["time"]["schedule"] = {"holidays": ["2026-01-01"]}
            elif not loc["time"]["schedule"].get("holidays"):
                loc["time"]["schedule"]["holidays"] = ["2026-01-01"]

        categories = provider.get("categories", [])
        for idx, category in enumerate(categories):
            cat_id = category.get("id", f"CAT00{idx+1}")
            if not CATEGORY_ID_REGEX.match(cat_id):
                category["id"] = f"CAT00{idx+1}"
        provider["categories"] = categories

        for item in provider.get("items", []):
            item["time"] = {"label": "enable", "timestamp": now_ts}

            item_desc = item.get("descriptor", {})
            if "code" not in item_desc or not (str(item_desc["code"]).startswith("1:") or str(item_desc["code"]).startswith("5:")):
                item_desc["code"] = "1:1001"
            item["descriptor"] = item_desc

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
            unit = str(measure.get("unit", "kilogram")).lower()
            if unit not in ALLOWED_UNITS:
                unit = "kilogram" if unit in ("kg", "kgs", "kilo") else "unit"
            measure["unit"] = unit
            measure["value"] = str(measure.get("value", "1"))
            unitized["measure"] = measure
            qty["unitized"] = unitized
            item["quantity"] = qty

            if "@ondc/org/statutory_reqs_prepackaged_food" in item:
                item["@ondc/org/statutory_reqs_prepackaged_food"] = _stringify_statutory_fields(
                    item["@ondc/org/statutory_reqs_prepackaged_food"]
                )

            parent_id = item.get("parent_item_id")
            if not isinstance(parent_id, str) or not parent_id.strip():
                item["parent_item_id"] = "V1"

            if not item.get("tags"):
                item["tags"] = DEFAULT_ITEM_TAGS

        if not isinstance(provider.get("creds"), list):
            provider["creds"] = [{
                "id": "C1",
                "type": "FSSAI",
                "url": "https://fssai.gov.in",
            }]
        if not isinstance(provider.get("offers"), list):
            provider["offers"] = [{
                "id": "O1",
                "descriptor": {"name": "5% Off on First Order"},
            }]

    cat["bpp/fulfillments"] = _build_catalog_fulfillments(providers)
    cat["bpp/providers"] = providers
    return cat


def _is_incremental_search(payload: dict) -> bool:
    """Detect incremental catalog refresh search from intent tags."""
    intent = payload.get("message", {}).get("intent", {})
    tags = intent.get("tags", [])
    for tag in tags:
        if tag.get("code") == "catalog_inc":
            return True
        for entry in tag.get("list", []):
            if entry.get("code") in ("start_time", "end_time"):
                return True
    return False


def _is_incremental_push(payload: dict) -> bool:
    """Detect incremental push search (Flow 8C)."""
    intent = payload.get("message", {}).get("intent", {})
    for tag in intent.get("tags", []):
        if tag.get("code") in ("catalog_inc", "bap_terms"):
            for entry in tag.get("list", []):
                if entry.get("code") == "mode" and entry.get("value") == "inc":
                    return True
    return False


class BppSearchService:
    def __init__(self):
        catalog_path = Path(__file__).parent.parent / "catalog" / "mock_catalog.json"
        with open(catalog_path, "r") as f:
            raw_catalog = json.load(f)
        self.mock_catalog = _normalize_catalog_quantities(raw_catalog)
        self._search_counts: dict = {}

    def _get_search_count(self, transaction_id: str) -> int:
        self._search_counts[transaction_id] = self._search_counts.get(transaction_id, 0) + 1
        return self._search_counts[transaction_id]

    async def process_search(self, payload: dict):
        """Asynchronously process the incoming search request and send on_search."""
        context = payload.get("context", {})
        transaction_id = context.get("transaction_id", "default_tx")
        search_count = self._get_search_count(transaction_id)

        await asyncio.sleep(0.5)

        normalized_catalog = _normalize_catalog_quantities(self.mock_catalog)

        # Incremental push flow: send 3 unsolicited on_search before the direct response.
        if search_count == 1 and (_is_incremental_push(payload) or _is_incremental_search(payload)):
            for _ in range(3):
                await bpp_client.send_unsolicited(context, "on_search", {"catalog": normalized_catalog})
                await asyncio.sleep(0.3)

        await bpp_client.send_callback(context, "on_search", {"catalog": normalized_catalog})

    async def handle_search(self, payload: dict):
        await self.process_search(payload)
        logger.info(f"Accepted /search request for transaction {payload.get('context', {}).get('transaction_id')}")


bpp_search_service = BppSearchService()
