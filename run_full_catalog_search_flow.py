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
print("Starting Search and Custom Menu (Full Catalog City) Flow")
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

# Step 1: Send Search Request
print(">>> Step 1: Sending /search request for Full Catalog City search...")
search_payload = {
    "transaction_id": transaction_id,
    "bpp_id": BPP_ID,
    "bpp_uri": BPP_URI,
    "query": "grocery"
}
res = requests.post(f"{BASE_URL}/search", json=search_payload)
check_status(res, "SEARCH")

print("Waiting 10 seconds for Step 2 on_search webhook to complete...")
time.sleep(10)

print("==================================================")
print("Search and Custom Menu (Full Catalog City) Flow Complete!")
print("Please check the Pramaan Sandbox UI.")
print("==================================================")
