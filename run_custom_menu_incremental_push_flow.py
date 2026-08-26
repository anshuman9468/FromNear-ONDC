import argparse
import datetime as dt
import json
import uuid
from datetime import timezone

BPP_URI = "https://ondc.fromnear.com/api/v1/ondc"
WORKBENCH_BAP_URI = "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/buyer"


def iso_now(offset_minutes: int = 0) -> str:
    value = dt.datetime.now(timezone.utc) + dt.timedelta(minutes=offset_minutes)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def build_search_payload(transaction_id: str, search_no: int) -> dict:
    tags = [
        {
            "code": "catalog_inc",
            "list": [
                {"code": "mode", "value": "inc"},
                {"code": "start_time", "value": iso_now(-30)},
                {"code": "end_time", "value": iso_now()},
            ],
        }
    ]
    if search_no == 1:
        tags[0]["list"] = [{"code": "mode", "value": "inc"}]

    return {
        "context": {
            "action": "search",
            "bap_id": "workbench.ondc.tech",
            "bap_uri": WORKBENCH_BAP_URI,
            "bpp_id": "ondc.fromnear.com",
            "bpp_uri": BPP_URI,
            "city": "std:080",
            "core_version": "1.2.0",
            "country": "IND",
            "domain": "ONDC:RET10",
            "message_id": f"custom-menu-push-search-{search_no}-{uuid.uuid4()}",
            "timestamp": iso_now(),
            "transaction_id": transaction_id,
            "ttl": "PT30S",
        },
        "message": {
            "intent": {
                "fulfillment": {
                    "type": "Delivery",
                    "end": {
                        "location": {
                            "gps": "12.971599,77.594563",
                            "address": {"area_code": "560001"},
                        }
                    },
                },
                "payment": {"@ondc/org/buyer_app_finder_fee_type": "percent", "@ondc/org/buyer_app_finder_fee_amount": "3"},
                "tags": tags,
            }
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Workbench JSON for Search and Custom Menu Incremental Push.")
    parser.add_argument("--post-to-bpp", action="store_true", help="POST generated search payloads to this BPP endpoint for local smoke testing.")
    args = parser.parse_args()

    transaction_id = f"custom-menu-push-{uuid.uuid4()}"
    payloads = [build_search_payload(transaction_id, 1), build_search_payload(transaction_id, 2)]

    for idx, payload in enumerate(payloads, start=1):
        print(f"\n=== Workbench search payload for step {1 if idx == 1 else 5} ===")
        print(json.dumps(payload, indent=2))

    if args.post_to_bpp:
        import requests

        for idx, payload in enumerate(payloads, start=1):
            response = requests.post(f"{BPP_URI}/search", json=payload, timeout=20)
            print(f"\nPOST search {idx}: {response.status_code}")
            print(response.text[:1000])


if __name__ == "__main__":
    main()
