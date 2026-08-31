import requests
import time
import uuid
import datetime
from datetime import timezone

# Configuration
BASE_URL = "https://ondc.fromnear.com/api/v1"
BPP_ID = "ondc.fromnear.com"
BPP_URI = "https://ondc.fromnear.com/api/v1/ondc"

# Generate new transaction ID
transaction_id = str(uuid.uuid4())
print("==================================================")
print("Starting Search and Custom Menu (Incremental Push) Flow")
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
        if isinstance(data, dict) and "gateway_response" in data and "412" in data.get("gateway_response", ""):
            print("==========================================================")
            print("⚠️ PRAMAAN SESSION TIMED OUT (Error 412)")
            print("Pramaan Sandbox only accepts requests for 60 seconds after")
            print("you click the Play (▶) button in the UI.")
            print("👉 Please click Play (▶) in Pramaan UI, then run this script.")
            print("==========================================================")
        print(f"!!! Error in {step_name}. Halting flow.")
        exit(1)

# Step 1: Initial /search (incremental push - full catalog)
print(">>> Step 1: Sending 1st /search request (incremental push)...")
search_payload_1 = {
    "transaction_id": transaction_id,
    "bpp_id": BPP_ID,
    "bpp_uri": BPP_URI,
    "query": "grocery",
    "mode": "start"
}
res = requests.post(f"{BASE_URL}/search", json=search_payload_1)
check_status(res, "SEARCH 1")

# Wait for Steps 2, 3, 4: on_search (x3 UNSOLICITED MOCK) from BPP
print("Waiting 15 seconds for Steps 2-4 (3x on_search) from mock BPP...")
time.sleep(15)

# Step 5: 2nd /search (incremental push - custom menu / delta)
print(">>> Step 5: Sending 2nd /search request (custom menu / incremental delta)...")
now_utc = datetime.datetime.now(timezone.utc)
start_time = (now_utc - datetime.timedelta(minutes=30)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
end_time = now_utc.isoformat(timespec="milliseconds").replace("+00:00", "Z")

search_payload_2 = {
    "transaction_id": transaction_id,
    "bpp_id": BPP_ID,
    "bpp_uri": BPP_URI,
    "query": "grocery",
    "mode": "start",
    "start_time": start_time,
    "end_time": end_time
}
res = requests.post(f"{BASE_URL}/search", json=search_payload_2)
check_status(res, "SEARCH 2")

print("Waiting 10 seconds for final on_search webhooks...")
time.sleep(10)

print("==================================================")
print("Search and Custom Menu (Incremental Push) Flow Complete!")
print("Please check the Pramaan Sandbox UI.")
print("==================================================")
