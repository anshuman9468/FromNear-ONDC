import json
import logging
import asyncio
import copy
import re
from pathlib import Path
from app.core.settings import settings
from app.ondc.bpp.client import bpp_client
from app.ondc.bpp.order_builder import _now
from app.ondc.protocol.item_identity import resolve_item_identity

logger = logging.getLogger(__name__)

ALLOWED_PROVIDER_TAG_CODES = {"timing", "close_timing", "serviceability", "order_value", "np_fees"}
ALLOWED_ITEM_TAG_CODES = {"origin", "veg_nonveg", "image", "timing", "np_fees"}
CATEGORY_ID_REGEX = re.compile(r"^[a-zA-Z0-9]{1,12}$")
ALLOWED_UNITS = {"unit", "dozen", "gram", "kilogram", "tonne", "litre", "millilitre"}
VALID_FULFILLMENT_TYPES = {"Delivery", "Self-Pickup"}
ALLOWED_OFFER_DESCRIPTOR_CODES = {"discount", "buyXgetY", "freebie", "slab", "combo", "delivery"}
FSSAI_LICENSE_NO = "12345678901234"

DEFAULT_STATUTORY_REQUIREMENTS = {
    "nutritional_info": "Nutritional information available on product packaging",
    "additives_info": "No artificial additives declared",
    "brand_owner_FSSAI_license_no": FSSAI_LICENSE_NO,
}

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
        "code": "np_fees",
        "list": [{"code": "id", "value": "FINDER_FEE"}],
    }
]


def _catalog_hours_range() -> dict:
    """Return the RET10 catalog operating range in the active HHMM format."""
    return {"start": "0900", "end": "2100"}


def _stringify_statutory_fields(statutory: dict) -> dict:
    """Ensure all statutory_reqs_prepackaged_food values are non-empty strings."""
    result = dict(DEFAULT_STATUTORY_REQUIREMENTS)
    for key, value in (statutory or {}).items():
        result[key] = str(value) if value is not None and str(value).strip() else result.get(key, "Not applicable")
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

    desc = dict(cat.get("bpp/descriptor") or {})
    desc["name"] = str(desc.get("name") or "FromNear Grocery")
    desc["symbol"] = str(desc.get("symbol") or "https://ondc.fromnear.com/assets/logo.png")
    desc["short_desc"] = str(desc.get("short_desc") or "Everyday grocery essentials from FromNear")
    desc["long_desc"] = str(desc.get("long_desc") or "FromNear provides grocery products with reliable local delivery.")
    desc["images"] = desc.get("images") if isinstance(desc.get("images"), list) else []
    desc_tags = desc.get("tags") if isinstance(desc.get("tags"), list) else []
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

        provider["tags"] = [
            t for t in provider.get("tags", [])
            if isinstance(t, dict) and t.get("code") in ALLOWED_PROVIDER_TAG_CODES
        ]

        for loc in provider.get("locations", []):
            if "time" not in loc:
                loc["time"] = {}
            loc["time"]["label"] = loc["time"].get("label", "enable")
            loc["time"]["timestamp"] = now_ts
            days = loc["time"].get("days")
            if isinstance(days, list):
                loc["time"]["days"] = ",".join(str(day) for day in days)
            elif isinstance(days, str) and days.strip():
                loc["time"]["days"] = days
            else:
                loc["time"]["days"] = "1,2,3,4,5,6,7"
            loc["time"]["range"] = _catalog_hours_range()
            if "schedule" not in loc["time"]:
                loc["time"]["schedule"] = {"holidays": ["2026-01-01"], "times": ["0900", "2100"]}
            else:
                loc["time"]["schedule"]["times"] = loc["time"]["schedule"].get("times") or ["0900", "2100"]
                if not loc["time"]["schedule"].get("holidays"):
                    loc["time"]["schedule"]["holidays"] = ["2026-01-01"]

        categories = provider.get("categories", [])
        for idx, category in enumerate(categories):
            cat_id = category.get("id", f"CAT00{idx+1}")
            if not CATEGORY_ID_REGEX.match(cat_id):
                category["id"] = f"CAT00{idx+1}"
            descriptor = category.get("descriptor")
            category["descriptor"] = descriptor if isinstance(descriptor, dict) else {
                "name": "Atta, Flours and Sooji"
            }
            category["tags"] = category.get("tags") if isinstance(category.get("tags"), list) else []
        # All purchasable variants in the mock catalog have parent_item_id V1.
        # Advertise that parent explicitly so catalog consumers can resolve it.
        if not any(category.get("id") == "V1" for category in categories if isinstance(category, dict)):
            categories.append({
                "id": "V1",
                "descriptor": {"name": "Product Variants"},
                "tags": [{"code": "type", "list": [{"code": "type", "value": "variant_group"}]}],
            })
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

            item["@ondc/org/statutory_reqs_prepackaged_food"] = _stringify_statutory_fields(
                item.get("@ondc/org/statutory_reqs_prepackaged_food")
            )

            # RET10 catalog and callback payloads use location_id. Accept the
            # legacy input alias but never emit it, otherwise Workbench builds
            # select/init/confirm requests with an invalid `location` field.
            location_ids = [
                str(location.get("id"))
                for location in provider.get("locations", [])
                if isinstance(location, dict) and location.get("id")
            ]
            fulfillment_ids = [
                str(fulfillment.get("id"))
                for fulfillment in provider.get("fulfillments", [])
                if isinstance(fulfillment, dict) and fulfillment.get("id")
            ]
            identity = resolve_item_identity(
                item,
                default_location_id=location_ids[0] if len(location_ids) == 1 else None,
                default_fulfillment_id=fulfillment_ids[0] if len(fulfillment_ids) == 1 else None,
            )
            item.update(identity)
            item.pop("location", None)

            item["tags"] = [
                tag for tag in item.get("tags", [])
                if isinstance(tag, dict) and tag.get("code") in ALLOWED_ITEM_TAG_CODES
            ]
            if not item["tags"]:
                # Give each item its own copy so a later serializer cannot
                # mutate the shared fallback for every catalog item.
                item["tags"] = copy.deepcopy(DEFAULT_ITEM_TAGS)

        raw_creds = provider.get("creds") if isinstance(provider.get("creds"), list) else [{}]
        provider["creds"] = [
            {
                **(cred if isinstance(cred, dict) else {}),
                "id": str((cred if isinstance(cred, dict) else {}).get("id") or f"C{index + 1}"),
                "type": str((cred if isinstance(cred, dict) else {}).get("type") or "FSSAI"),
                "url": str((cred if isinstance(cred, dict) else {}).get("url") or "https://fssai.gov.in"),
                "descriptor": {
                    **((cred if isinstance(cred, dict) else {}).get("descriptor", {})),
                    "code": str(((cred if isinstance(cred, dict) else {}).get("descriptor", {}) or {}).get("code") or "FSSAI"),
                    "name": str(((cred if isinstance(cred, dict) else {}).get("descriptor", {}) or {}).get("name") or "FSSAI License"),
                },
                "tags": ((cred if isinstance(cred, dict) else {}).get("tags")
                         if isinstance((cred if isinstance(cred, dict) else {}).get("tags"), list) else []),
            }
            for index, cred in enumerate(raw_creds)
        ]

        item_ids = [str(item.get("id")) for item in provider.get("items", []) if item.get("id")]
        location_ids = [str(location.get("id")) for location in provider.get("locations", []) if location.get("id")]
        raw_offers = provider.get("offers") if isinstance(provider.get("offers"), list) else [{}]
        provider["offers"] = [
            {
                **(offer if isinstance(offer, dict) else {}),
                "id": str((offer if isinstance(offer, dict) else {}).get("id") or f"O{index + 1}"),
                "descriptor": {
                    **((offer if isinstance(offer, dict) else {}).get("descriptor", {})),
                    "code": (
                        str(((offer if isinstance(offer, dict) else {}).get("descriptor", {}) or {}).get("code"))
                        if str(((offer if isinstance(offer, dict) else {}).get("descriptor", {}) or {}).get("code"))
                        in ALLOWED_OFFER_DESCRIPTOR_CODES
                        else "discount"
                    ),
                    "name": str(((offer if isinstance(offer, dict) else {}).get("descriptor", {}) or {}).get("name") or "Store Offer"),
                    "images": (((offer if isinstance(offer, dict) else {}).get("descriptor", {}) or {}).get("images")
                               if isinstance(((offer if isinstance(offer, dict) else {}).get("descriptor", {}) or {}).get("images"), list) else []),
                },
                "location_ids": ((offer if isinstance(offer, dict) else {}).get("location_ids")
                                 if isinstance((offer if isinstance(offer, dict) else {}).get("location_ids"), list) else location_ids),
                "item_ids": ((offer if isinstance(offer, dict) else {}).get("item_ids")
                             if isinstance((offer if isinstance(offer, dict) else {}).get("item_ids"), list) else item_ids),
                "time": {
                    "label": "enable",
                    "range": {"start": "0900", "end": "2100"},
                },
                "tags": ((offer if isinstance(offer, dict) else {}).get("tags")
                         if isinstance((offer if isinstance(offer, dict) else {}).get("tags"), list) else []),
            }
            for index, offer in enumerate(raw_offers)
        ]

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
                # Flow 8C brackets the push sequence with mode=start/stop.
                # Do not classify the separate pull-refresh mode=inc flow as
                # push.
                if entry.get("code") == "mode" and entry.get("value") in {"start", "stop"}:
                    return True
    return False


def _is_custom_menu_push_flow(payload: dict | None = None) -> bool:
    if _is_incremental_push(payload or {}):
        return True
    return (settings.ONDC_BPP_FLOW_MODE or "auto").lower() in {
        "custom_menu_push",
        "incremental_push",
        "catalog_push",
    }


def _make_incremental_catalog(catalog: dict, search_count: int) -> dict:
    """Create a stable catalog snapshot for incremental custom-menu pushes."""
    pushed_catalog = _normalize_catalog_quantities(catalog)
    providers = pushed_catalog.get("bpp/providers", [])
    if not providers:
        return pushed_catalog

    provider = providers[0]
    provider["ttl"] = "PT15M"
    provider["time"]["timestamp"] = _now()

    items = provider.get("items", [])
    if search_count >= 2 and items:
        # Second Workbench search is the delta/custom-menu update.
        provider["items"] = [
            {
                **items[0],
                "id": items[0].get("id", "I1"),
                "descriptor": {
                    **items[0].get("descriptor", {}),
                    "name": "Updated Custom Menu - Atta Whole Wheat Flour 5kg",
                },
                "price": {
                    **items[0].get("price", {}),
                    "currency": "INR",
                    "value": "245.00",
                    "maximum_value": "250.00",
                },
                "time": {"label": "enable", "timestamp": _now()},
            }
        ]
    return pushed_catalog


def _align_catalog_area_code(catalog: dict, payload: dict) -> dict:
    """Use the requested delivery area for gateway city/serviceability checks."""
    intent = payload.get("message", {}).get("intent", {})
    fulfillment = intent.get("fulfillment", {}) if isinstance(intent, dict) else {}
    end_location = fulfillment.get("end", {}).get("location", {})
    address = end_location.get("address", {}) if isinstance(end_location, dict) else {}
    area_code = str(address.get("area_code") or "").strip()
    if not area_code:
        return catalog

    aligned = copy.deepcopy(catalog)
    for provider in aligned.get("bpp/providers", []):
        for location in provider.get("locations", []):
            location.setdefault("address", {})["area_code"] = area_code
    return aligned


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

        normalized_catalog = _make_incremental_catalog(self.mock_catalog, search_count)
        normalized_catalog = _align_catalog_area_code(normalized_catalog, payload)

        if _is_custom_menu_push_flow(payload):
            # Workbench records the first on_search as the direct response to
            # /search, then accepts the remaining catalog deltas as pushes.
            # The final Workbench search only verifies the pushed catalog; it
            # does not have an on_search response step. Sending another
            # callback there creates an out-of-sequence event.
            if search_count > 1:
                return
            await bpp_client.send_callback(context, "on_search", {"catalog": normalized_catalog})
            push_count = 2 if search_count == 1 else 0
            for _ in range(push_count):
                # Give Workbench time to commit the preceding callback before
                # recording the next unsolicited catalog update.
                await asyncio.sleep(0.5)
                await bpp_client.send_unsolicited(context, "on_search", {"catalog": normalized_catalog})
            return

        # Pull refresh is a pair of synchronous /search -> on_search calls.
        # Only the explicit custom-menu push mode above emits unsolicited
        # catalog deltas; sending them here creates out-of-sequence callbacks.
        await bpp_client.send_callback(context, "on_search", {"catalog": normalized_catalog})

    async def handle_search(self, payload: dict):
        await self.process_search(payload)
        logger.info(f"Accepted /search request for transaction {payload.get('context', {}).get('transaction_id')}")


bpp_search_service = BppSearchService()
