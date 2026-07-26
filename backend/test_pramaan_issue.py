import requests
import json
import uuid
import datetime
from datetime import timezone

bpp_uri = "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/seller"
url = f"{bpp_uri}/issue"

# Generate test payload
txn_id = str(uuid.uuid4())
msg_id = str(uuid.uuid4())
iss_id = str(uuid.uuid4())
now = datetime.datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def test_payload(domain, core_version, include_bap_id=True, rating=None):
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
        "bpp_id": "workbench.ondc.tech",
        "complainant_info": {
            "person": {"name": "Jane Doe"},
            "contact": {
                "phone": "9876543210",
                "email": "buyer@example.com"
            }
        },
        "order_details": {
            "id": "order_123",
            "state": "Completed",
            "items": [{"id": "I1", "quantity": 1}],
            "fulfillments": [{"id": "F1", "state": "Order-delivered"}],
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
                        "org": {"name": "ondc.fromnear.com::ONDC:RET10"},
                        "contact": {
                            "phone": "9876543210",
                            "email": "buyer@example.com"
                        },
                        "person": {"name": "Jane Doe"}
                    }
                }
            ]
        },
        "created_at": now,
        "updated_at": now
    }
    if include_bap_id:
        issue_obj["bap_id"] = "ondc.fromnear.com"
    if rating:
        issue_obj["rating"] = rating
        
    payload = {"context": context, "message": {"issue": issue_obj}}
    
    res = requests.post(url, json=payload)
    print(f"Domain={domain}, Version={core_version}, bap_id={include_bap_id}, rating={rating} -> Status: {res.status_code}, Res: {res.text}")

print("Testing different payload structures directly against Pramaan...")
test_payload("ONDC:RET10", "1.0.0")
test_payload("nic2004:52110", "1.0.0")
test_payload("ONDC:RET10", "1.2.0")
test_payload("nic2004:52110", "1.0.0", include_bap_id=True, rating="THUMBS-DOWN")
