import json
from pathlib import Path
from app.ondc.bpp.order_builder import _now
from app.core.settings import settings

catalog_path = Path("app/ondc/bpp/catalog/mock_catalog.json")
with open(catalog_path, "r") as f:
    mock_catalog = json.load(f)

on_search_payload = {
    "context": {
        "domain": "ONDC:RET10",
        "country": "IND",
        "city": "std:080",
        "action": "on_search",
        "core_version": "1.2.0",
        "bap_id": "workbench.ondc.tech",
        "bap_uri": "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/buyer",
        "bpp_id": settings.ONDC_SUBSCRIBER_ID,
        "bpp_uri": settings.ONDC_SUBSCRIBER_URI,
        "transaction_id": "48813e2f-8767-4899-b957-767d808e34e8",
        "message_id": "037b6559-25b3-47c1-ad17-88eafef42df7",
        "timestamp": _now(),
        "ttl": "PT30S"
    },
    "message": {
        "catalog": mock_catalog
    }
}

print(json.dumps(on_search_payload, indent=2))
