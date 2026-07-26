import requests
import time
import uuid

# Configuration
BASE_URL = "https://ondc.fromnear.com/api/v1"
BPP_ID = "workbench.ondc.tech"
BPP_URI = "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/seller"

# Generate new transaction ID
transaction_id = str(uuid.uuid4())
print(f"==================================================")
print(f"Starting ONDC Update Flow")
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

print("Waiting 6 seconds for on_select webhook...")
time.sleep(6)

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

print("Waiting 6 seconds for on_init webhook...")
time.sleep(6)

# 3. CONFIRM
print(">>> Step 3: Sending /confirm request...")
confirm_payload = {
    "transaction_id": transaction_id
}
res = requests.post(f"{BASE_URL}/confirm", json=confirm_payload)
check_status(res, "CONFIRM")

print("Waiting 75 seconds for automated on_status webhooks (Steps 7-12) to complete before 1st update...")
time.sleep(75)

# 4. UPDATE 1 (Step 13)
print(">>> Step 13: Sending 1st /update request...")
update_payload = {
    "transaction_id": transaction_id,
    "update_target": "item"
}
res = requests.post(f"{BASE_URL}/update", json=update_payload)
check_status(res, "UPDATE 1")

print("Waiting 40 seconds for on_update webhooks (Steps 14, 15, 16) to complete before 2nd update...")
time.sleep(40)

# 5. UPDATE 2 (Step 17) — confirm return pickup by buyer
# Step 16 on_update from mock seller sets Return fulfillment to Return_Picked.
# Step 17 buyer confirms return item received back → update_target=fulfillment
# We pass a custom_order with ONLY the Return fulfillment (state=Return_Delivered).
print(">>> Step 17: Sending 2nd /update request...")
update_payload2 = {
    "transaction_id": transaction_id,
    "update_target": "fulfillment",
    "order": {
        "fulfillments": [
            {
                "id": "646428",
                "type": "Return",
                "state": {
                    "descriptor": {
                        "code": "Return_Delivered"
                    }
                }
            }
        ],
        "items": [
            {"id": "I1", "quantity": {"count": 1}}
        ]
    }
}
res = requests.post(f"{BASE_URL}/update", json=update_payload2)
check_status(res, "UPDATE 2")

print("Waiting 10 seconds for final on_update webhook (Step 18) to complete in Pramaan UI...")
time.sleep(10)

print("==================================================")
print("Update Flow Complete! Please check Pramaan Sandbox UI.")
print("==================================================")
