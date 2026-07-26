import requests
import json
import uuid
import datetime
from datetime import timezone

txn_id = "ecbf0ed9-d748-4270-b0b3-3d89a073f75f"
msg_id = str(uuid.uuid4())
iss_id = str(uuid.uuid4())
now = datetime.datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def make_payload(domain, core_version, bpp_uri):
    context = {
        "domain": domain,
        "country": "IND",
        "city": "std:080",
        "action": "issue",
        "core_version": core_version,
        "bap_id": "ondc.fromnear.com",
        "bap_uri": "https://ondc.fromnear.com/api/v1/ondc",
        "bpp_id": "workbench.ondc.tech",
        "bpp_uri": bpp_uri,
        "transaction_id": txn_id,
        "message_id": msg_id,
        "timestamp": now,
        "ttl": "PT30S"
    }
    
    issue_obj = {
        "id": iss_id,
        "category": "ITEM",
        "sub_category": "ITM01",
        "bap_id": "ondc.fromnear.com",
        "bpp_id": "workbench.ondc.tech",
        "complainant_info": {
            "person": {"name": "Jane Doe"},
            "contact": {"phone": "9876543210", "email": "buyer@example.com"}
        },
        "order_details": {
            "id": "bd92ec02-2bd9-49de-afc4-b85eb6a5658e",
            "state": "In-progress",
            "items": [{"id": "I1", "quantity": 1}],
            "fulfillments": [{"id": "F1", "state": "Order-picked-up"}],
            "provider_id": "P1"
        },
        "description": {
            "short_desc": "Issue with item quality",
            "long_desc": "Detailed issue with item quality",
            "additional_desc": {
                "url": "https://ondc.fromnear.com/proof.jpg",
                "content_type": "text/plain"
            },
            "images": ["https://ondc.fromnear.com/proof.jpg"]
        },
        "source": {
            "network_participant_id": "ondc.fromnear.com",
            "type": "CONSUMER"
        },
        "expected_response_time": {"duration": "PT2H"},
        "expected_resolution_time": {"duration": "P1D"},
        "status": "OPEN",
        "issue_type": "ISSUE",
        "issue_actions": {
            "complainant_actions": [
                {
                    "complainant_action": "OPEN",
                    "short_desc": "Complaint created",
                    "updated_at": now,
                    "updated_by": {
                        "org": {"name": f"ondc.fromnear.com::{domain}"},
                        "contact": {"phone": "9876543210", "email": "buyer@example.com"},
                        "person": {"name": "Jane Doe"}
                    }
                }
            ]
        },
        "created_at": now,
        "updated_at": now
    }
    return {"context": context, "message": {"issue": issue_obj}}

bpp_uris = [
    "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/seller",
    "https://workbench.ondc.tech/api-service/nic2004:52110/1.0.0/seller"
]

domains = ["nic2004:52110", "ONDC:RET10"]
versions = ["1.0.0", "1.2.0"]

for uri in bpp_uris:
    for d in domains:
        for v in versions:
            url = f"{uri}/issue"
            p = make_payload(d, v, uri)
            try:
                res = requests.post(url, json=p, timeout=5)
                print(f"URL: {url} | Domain: {d} | Version: {v} -> Status: {res.status_code}, Res: {res.text[:150]}")
            except Exception as e:
                print(f"Error: {e}")

