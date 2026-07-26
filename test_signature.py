"""
Direct test: Sign a select payload locally and send it straight to Workbench.
This bypasses the Cloud Run backend to isolate the signing issue.
"""
import requests
import json
import time
import uuid
import base64
import hashlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# ─── Keys & Subscriber Info ───────────────────────────────────────────────────
SIGNING_PRIVATE_KEY_B64 = "midAN7ykDVbtOVIKJpwEGV0Tma5VOfQpeiBrYbRVhJ5AkJUMn9Z9yqlNTEbcSk4SHZnnCCbPpDW/Kqqn06zstA=="
SUBSCRIBER_ID = "ondc.fromnear.com"
UNIQUE_KEY_ID = "8c5c6504-113b-4150-acb0-6e2577c972ca"

BPP_ID  = "workbench.ondc.tech"
BPP_URI = "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/seller"

# ─── Build Select Payload ─────────────────────────────────────────────────────
transaction_id = str(uuid.uuid4())
message_id     = str(uuid.uuid4())

payload = {
    "context": {
        "domain": "ONDC:RET10",
        "country": "IND",
        "city": "std:080",
        "action": "select",
        "core_version": "1.2.0",
        "bap_id": SUBSCRIBER_ID,
        "bap_uri": f"https://{SUBSCRIBER_ID}/api/v1/ondc",
        "bpp_id": BPP_ID,
        "bpp_uri": BPP_URI,
        "transaction_id": transaction_id,
        "message_id": message_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "ttl": "PT30S",
    },
    "message": {
        "order": {
            "provider": {
                "id": "P1",
                "locations": [{"id": "L1"}]
            },
            "items": [
                {"id": "I1", "quantity": {"count": 1}, "location_id": "L1"}
            ],
            "fulfillments": [{
                "end": {
                    "location": {
                        "gps": "12.9716,77.5946",
                        "address": {"area_code": "560001"}
                    }
                }
            }]
        }
    }
}

# ─── Sign ─────────────────────────────────────────────────────────────────────
body_bytes = json.dumps(payload, separators=(',', ':')).encode("utf-8")

h = hashlib.blake2b(digest_size=64)
h.update(body_bytes)
digest = "BLAKE-512=" + base64.b64encode(h.digest()).decode("utf-8")

created = int(time.time())
expires = created + 300
signing_string = f"(created): {created}\n(expires): {expires}\ndigest: {digest}".encode("utf-8")

raw_key = base64.b64decode(SIGNING_PRIVATE_KEY_B64)
private_key = Ed25519PrivateKey.from_private_bytes(raw_key[:32])
signature = base64.b64encode(private_key.sign(signing_string)).decode("utf-8")

auth_header = (
    f'Signature keyId="{SUBSCRIBER_ID}|{UNIQUE_KEY_ID}|ed25519",'
    f'algorithm="ed25519",'
    f'created="{created}",'
    f'expires="{expires}",'
    f'headers="(created) (expires) digest",'
    f'signature="{signature}"'
)

# ─── Send ─────────────────────────────────────────────────────────────────────
url = f"{BPP_URI}/select"
headers = {
    "Content-Type": "application/json",
    "Authorization": auth_header,
}

print(f"Transaction ID : {transaction_id}")
print(f"Signing string :\n{signing_string.decode()}")
print(f"\nAuth Header:\n{auth_header}\n")
print(f"Sending to: {url}")
print("-" * 60)

res = requests.post(url, data=body_bytes, headers=headers)
print(f"HTTP Status : {res.status_code}")
try:
    print(f"Response    : {json.dumps(res.json(), indent=2)}")
except Exception:
    print(f"Response    : {res.text}")
