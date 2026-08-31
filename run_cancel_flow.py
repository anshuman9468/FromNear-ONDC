import requests
import time
import uuid

# Configuration
BASE_URL = "https://ondc.fromnear.com/api/v1"
BPP_ID = "ondc.fromnear.com"
BPP_URI = "https://ondc.fromnear.com/api/v1/ondc"

# Generate new transaction ID
transaction_id = str(uuid.uuid4())
print(f"==================================================")
print(f"Starting Buyer Side Order Cancellation Flow")
print(f"Transaction ID: {transaction_id}")
print(f"==================================================\n")

def check_status(response, step_name):
    print(f"[{step_name}] Status Code: {response.status_code}")
    data = None
    try:
        data = response.json()
        print(f"[{step_name}] Response: {data}\n")
    except:
        print(f"[{step_name}] Response: {response.text}\n")
    if response.status_code >= 400 or (
        isinstance(data, dict)
        and data.get("status") in {"GATEWAY_ERROR", "NACK"}
    ):
        print(f"!!! Error in {step_name}. Halting flow.")
        exit(1)

# 1. SELECT
print(">>> Step 1: Sending /select request...")
select_payload = {
    "transaction_id": transaction_id,
    "bpp_id": BPP_ID,
    "bpp_uri": BPP_URI,
    "provider_id": "P1",
    "provider_name": "Mock Provider",
    "items": [
        {
            "id": "I1",
            "name": "shoes",
            "quantity": 1,
            "price": 500.0
        }
    ]
}
res = requests.post(f"{BASE_URL}/select", json=select_payload)
check_status(res, "SELECT")

print("Waiting 5 seconds for on_select webhook...")
time.sleep(5)

# 2. INIT
print(">>> Step 2: Sending /init request...")
init_payload = {
    "transaction_id": transaction_id,
    "billing_address": {
      "name": "Jane Doe",
      "phone": "9876543210",
      "house": "Apt 4B",
      "street": "MG Road",
      "city": "Bengaluru",
      "state": "Karnataka",
      "pincode": "560001"
    },
    "shipping_address": {
      "name": "Jane Doe",
      "phone": "9876543210",
      "house": "Apt 4B",
      "street": "MG Road",
      "city": "Bengaluru",
      "state": "Karnataka",
      "pincode": "560001"
    }
}
res = requests.post(f"{BASE_URL}/init", json=init_payload)
check_status(res, "INIT")

print("Waiting 5 seconds for on_init webhook...")
time.sleep(5)

# 3. CONFIRM
print(">>> Step 3: Sending /confirm request...")
confirm_payload = {
    "transaction_id": transaction_id
}
res = requests.post(f"{BASE_URL}/confirm", json=confirm_payload)
check_status(res, "CONFIRM")

print("Waiting 5 seconds for on_confirm webhook...")
time.sleep(5)

# 4. CANCEL (Step 7)
print(">>> Step 4: Sending /cancel request...")
cancel_payload = {
    "transaction_id": transaction_id,
    "cancellation_reason_id": "002"
}
res = requests.post(f"{BASE_URL}/cancel", json=cancel_payload)
check_status(res, "CANCEL")

print("Waiting 5 seconds for on_cancel webhook...")
time.sleep(5)

print("==================================================")
print("Buyer Side Cancellation Flow Complete!")
print("Please check the Pramaan Sandbox UI.")
print("==================================================")
