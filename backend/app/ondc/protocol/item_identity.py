"""Canonical RET10 item references shared by buyer and seller serializers."""

from typing import Any, Dict, Optional


class ItemIdentityError(ValueError):
    """Raised when an item cannot be mapped to the catalog identity it needs."""


def _non_empty_string(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def resolve_item_identity(
    item: Dict[str, Any],
    *,
    catalog_item: Optional[Dict[str, Any]] = None,
    default_location_id: Optional[str] = None,
    default_fulfillment_id: Optional[str] = None,
) -> Dict[str, str]:
    """Resolve an item using its own fields and the matching catalog item.

    ``location`` is accepted only as a backward-compatible input alias. It is
    never emitted. Parent identity is never inferred from an item index,
    category, or arbitrary default; it must be present in the selected item or
    in the catalog record for that item.
    """
    source = item if isinstance(item, dict) else {}
    embedded_catalog = source.get("catalog_item")
    candidates = [source]
    if isinstance(embedded_catalog, dict):
        candidates.append(embedded_catalog)
    if isinstance(catalog_item, dict) and catalog_item is not embedded_catalog:
        candidates.append(catalog_item)

    def first(*keys: str) -> Optional[str]:
        for candidate in candidates:
            for key in keys:
                value = _non_empty_string(candidate.get(key))
                if value:
                    return value
        return None

    item_id = first("id")
    location_id = first("location_id", "location") or _non_empty_string(default_location_id)
    parent_item_id = first("parent_item_id", "parent_id")
    fulfillment_id = first("fulfillment_id") or _non_empty_string(default_fulfillment_id)

    missing = [
        name
        for name, value in (
            ("id", item_id),
            ("location_id", location_id),
            ("parent_item_id", parent_item_id),
            ("fulfillment_id", fulfillment_id),
        )
        if not value
    ]
    if missing:
        raise ItemIdentityError(
            f"Item {item_id or '<unknown>'} is missing canonical RET10 reference(s): "
            + ", ".join(missing)
        )

    return {
        "id": item_id,
        "location_id": location_id,
        "parent_item_id": parent_item_id,
        "fulfillment_id": fulfillment_id,
    }
