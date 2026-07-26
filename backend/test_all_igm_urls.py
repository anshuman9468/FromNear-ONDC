import requests
import json
import uuid
import datetime
from datetime import timezone

txn_id = str(uuid.uuid4())
msg_id = str(uuid.uuid4())
iss_id = str(uuid.uuid4())
now = datetime.datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

payload = {
  "context": {
    "domain": "nic2004:52110",
    "country": "IND",
    "city": "std:080",
    "action": "issue",
    "core_version": "1.0.0",
    "bap_id": "ondc.fromnear.com",
    "bap_uri": "https://ondc.fromnear.com/api/v1/ondc",
    "bpp_id": "workbench.ondc.tech",
    "bpp_uri": "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/seller",
    "transaction_id": txn_id,
    "message_id": msg_id,
    "timestamp": now,
    "ttl": "PT30S"
  },
  "message": {
    "issue": {
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
              "org": {"name": "ondc.fromnear.com::nic2004:52110"},
              "contact": {"phone": "9876543210", "email": "buyer@example.com"},
              "person": {"name": "Jane Doe"}
            }
          }
        ]
      },
      "created_at": now,
      "updated_at": now
    }
  }
}

urls = [
    "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/seller/issue",
    "https://workbench.ondc.tech/api-service/ONDC:RET10/1.0.0/seller/issue",
    "https://workbench.ondc.tech/api-service/nic2004:52110/1.0.0/seller/issue",
    "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/issue",
    "https://workbench.ondc.tech/api-service/igm/1.0.0/seller/issue",
    "https://workbench.ondc.tech/api-service/igm/seller/issue"
]

for url in urls:
    try:
        res = requests.post(url, json=payload, timeout=5)
        print(f"URL: {url} -> Status: {res.status_code}, Body: {res.text[:200]}")
    except Exception as e:
        print(f"URL: {url} -> Error: {e}")
