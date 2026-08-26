import requests
import time
import uuid
import datetime
import os
from datetime import timezone

# Configuration
BASE_URL = "https://ondc.fromnear.com/api/v1"
BPP_ID = "workbench.ondc.tech"
BPP_URI = "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/seller"

# Generate new transaction ID
transaction_id = os.getenv("TRANSACTION_ID") or str(uuid.uuid4())
print("==================================================")
print("Starting Discovery Flow Incremental Catalog Refresh Pull")
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

# Step 1: Initial Search Request (Catalog Refresh Start)
print(">>> Step 1: Sending initial /search request (mode=start)...")
search_payload_1 = {
    "transaction_id": transaction_id,
    "bpp_id": BPP_ID,
    "bpp_uri": BPP_URI,
    "query": "grocery",
    "mode": "start"
}
res = requests.post(f"{BASE_URL}/search", json=search_payload_1)
check_status(res, "SEARCH 1")

print("Waiting 18 seconds for Step 2 on_search webhook to complete...")
time.sleep(18)

# Step 3: Incremental Search Request (Catalog Refresh Pull with timestamp)
print(">>> Step 3: Sending 2nd /search request for incremental catalog pull...")
now_utc = datetime.datetime.now(timezone.utc)
start_time = (now_utc - datetime.timedelta(minutes=30)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
end_time = now_utc.isoformat(timespec="milliseconds").replace("+00:00", "Z")

search_payload_2 = {
    "transaction_id": transaction_id,
    "bpp_id": BPP_ID,
    "bpp_uri": BPP_URI,
    "mode": "end",
    "start_time": start_time,
    "end_time": end_time
}
res = requests.post(f"{BASE_URL}/search", json=search_payload_2)
check_status(res, "SEARCH 2")

print("Waiting 5 seconds for Step 4 on_search webhook...")
time.sleep(5)

print("==================================================")
print("Incremental Catalog Refresh Pull Complete!")
print("Please check the Pramaan Sandbox UI.")
print("==================================================")
