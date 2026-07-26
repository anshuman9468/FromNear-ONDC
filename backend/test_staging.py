import requests
import json
from app.core.settings import settings
from app.ondc.crypto.utils import generate_auth_header
import time
import uuid

gateway_url = "https://staging.gateway.proteantech.in"

context = {
    "domain": "nic2004:52110",
    "country": "IND",
    "city": "std:080",
    "action": "search",
    "core_version": "1.2.0",
    "bap_id": settings.ONDC_SUBSCRIBER_ID,
    "bap_uri": settings.ONDC_SUBSCRIBER_URI,
    "transaction_id": str(uuid.uuid4()),
    "message_id": str(uuid.uuid4()),
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "ttl": "PT30S"
}
message = {
    "intent": {
        "item": {
            "descriptor": {
                "name": "shoes"
            }
        }
    }
}
payload = {"context": context, "message": message}
payload_json = json.dumps(payload, separators=(',', ':'))

auth_header = generate_auth_header(payload_json.encode("utf-8"))

headers = {
    "Content-Type": "application/json",
    "Authorization": auth_header,
    "X-Gateway-Authorization": auth_header
}

print(f"Testing {gateway_url}/search")
response = requests.post(f"{gateway_url}/search", json=payload, headers=headers)
print(response.status_code)
print(response.text)
