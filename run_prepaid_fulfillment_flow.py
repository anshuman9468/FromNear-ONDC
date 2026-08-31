import requests
import time
import uuid

# Configuration
BASE_URL = "https://ondc.fromnear.com/api/v1"
BPP_ID = "ondc.fromnear.com"
BPP_URI = "https://ondc.fromnear.com/api/v1/ondc"

# Generate new transaction ID
transaction_id = str(uuid.uuid4())
print("==================================================")
print("Starting Order to Confirm to Fulfillment (Prepaid) Flow")
print(f"Transaction ID: {transaction_id}")
print("==================================================\n")

def check_status(response, step_name):
    print(f"[{step_name}] Status Code: {response.status_code}")
    data = None
    try:
        data = response.json()
        print(f"[{step_name}] Response: {data}\n")
    except:
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

# Step 1: SELECT
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

print("Waiting 5 seconds for Step 2 on_select webhook...")
time.sleep(5)

# Step 3: INIT
print(">>> Step 3: Sending /init request...")
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

print("Waiting 5 seconds for Step 4 on_init webhook...")
time.sleep(5)

# Step 5: CONFIRM
print(">>> Step 5: Sending /confirm request...")
confirm_payload = {
    "transaction_id": transaction_id
}
res = requests.post(f"{BASE_URL}/confirm", json=confirm_payload)
check_status(res, "CONFIRM")

print("Waiting 30 seconds for automated on_status webhooks (Steps 7-10) to complete in Sandbox...")
time.sleep(30)

# Step 11: TRACK
print(">>> Step 11: Sending /track request...")
res = requests.get(f"{BASE_URL}/track?transaction_id={transaction_id}")
check_status(res, "TRACK")

print("Waiting 20 seconds for Step 12 on_track and remaining on_status webhooks (Steps 13-14)...")
time.sleep(20)

print("==================================================")
print("Order to Confirm to Fulfillment (Prepaid) Complete!")
print("Please check the Pramaan Sandbox UI.")
print("==================================================")
