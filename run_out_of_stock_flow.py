import requests
import time
import uuid

# Configuration
BASE_URL = "https://ondc.fromnear.com/api/v1"
BPP_ID = "workbench.ondc.tech"
BPP_URI = "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/seller"

# Generate new transaction ID
transaction_id = str(uuid.uuid4())
print("==================================================")
print("Starting Out of Stock (Error Code) Flow")
print(f"Transaction ID: {transaction_id}")
print("==================================================\n")

def check_status(response, step_name):
    print(f"[{step_name}] Status Code: {response.status_code}")
    data = None
    try:
        data = response.json()
        print(f"[{step_name}] Response: {data}\n")
    except Exception:
        print(f"[{step_name}] Response: {response.text}\n")
        
    if response.status_code >= 400 or (isinstance(data, dict) and data.get("status") in ["GATEWAY_ERROR", "NACK"]):
        if isinstance(data, dict) and "gateway_response" in data and "412" in data["gateway_response"]:
            print("==========================================================")
            print("⚠️ PRAMAAN SESSION TIMED OUT (Error 412)")
            print("Pramaan Sandbox only accepts requests for 60 seconds after")
            print("you click the Play (▶) button in the UI.")
            print("👉 Please click Play (▶) in Pramaan UI, then run this script.")
            print("==========================================================")
        print(f"!!! Error in {step_name}. Halting flow.")
        exit(1)

# Step 1: 1st SELECT
print(">>> Step 1: Sending 1st /select request...")
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
check_status(res, "1st SELECT")

print("Waiting 3 seconds for Step 2 on_select webhook...")
time.sleep(3)

# Step 3: 2nd SELECT
print(">>> Step 3: Sending 2nd /select request...")
res = requests.post(f"{BASE_URL}/select", json=select_payload)
check_status(res, "2nd SELECT")

print("Waiting 3 seconds for Step 4 on_select webhook...")
time.sleep(3)

# Step 5: INIT
print(">>> Step 5: Sending /init request...")
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

print("Waiting 3 seconds for Step 6 on_init webhook...")
time.sleep(3)

# Step 7: CONFIRM
print(">>> Step 7: Sending /confirm request...")
confirm_payload = {
    "transaction_id": transaction_id
}
res = requests.post(f"{BASE_URL}/confirm", json=confirm_payload)
check_status(res, "CONFIRM")

print("Waiting 30 seconds for automated on_status webhooks (Steps 9-12) to complete...")
time.sleep(30)

# Step 13: TRACK
print(">>> Step 13: Sending /track request...")
res = requests.get(f"{BASE_URL}/track?transaction_id={transaction_id}")
check_status(res, "TRACK")

print("Waiting 8 seconds for Step 14 (on_track) and automated on_status webhooks (Steps 15-16)...")
time.sleep(8)

print("==================================================")
print("Out of Stock (Error Code) Flow Complete!")
print("Please check the Pramaan Sandbox UI.")
print("==================================================")
