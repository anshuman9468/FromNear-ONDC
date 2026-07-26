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
print("Starting Order to confirm to fulfillment Prepaid with igm 1.0.0 Flow")
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

print("Waiting 3 seconds for Step 2 on_select webhook...")
time.sleep(3)

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

print("Waiting 3 seconds for Step 4 on_init webhook...")
time.sleep(3)

# Step 5: CONFIRM
print(">>> Step 5: Sending /confirm request...")
confirm_payload = {
    "transaction_id": transaction_id
}
res = requests.post(f"{BASE_URL}/confirm", json=confirm_payload)
check_status(res, "CONFIRM")

print("Waiting 30 seconds for automated on_status webhooks (Steps 7-10) to complete...")
time.sleep(30)

# Step 11: TRACK
print(">>> Step 11: Sending /track request...")
res = requests.get(f"{BASE_URL}/track?transaction_id={transaction_id}")
check_status(res, "TRACK")

print("Waiting 10 seconds for Step 12 on_track and on_status webhooks (Steps 13-14)...")
time.sleep(10)

# Step 15: ISSUE 1
print(">>> Step 15: Sending 1st /issue request (raising complaint)...")
res = requests.post(f"{BASE_URL}/issue?transaction_id={transaction_id}")
check_status(res, "ISSUE 1")

print("Waiting 10 seconds for Step 16 (on_issue) and Step 17 (on_issue_status)...")
time.sleep(10)

# Step 18: ISSUE 2
print(">>> Step 18: Sending 2nd /issue request (confirming resolution/update)...")
res = requests.post(f"{BASE_URL}/issue?transaction_id={transaction_id}")
check_status(res, "ISSUE 2")

print("Waiting 3 seconds for final processing...")
time.sleep(3)

print("==================================================")
print("Order to confirm to fulfillment Prepaid with igm 1.0.0 Flow Complete!")
print("Please check the Pramaan Sandbox UI.")
print("==================================================")
