import requests

url = "https://fromnear-ondc-backend-283058635167.us-central1.run.app/api/v1/issue?transaction_id=non_existent_txn"
res = requests.post(url)
print("Status Code:", res.status_code)
print("Response:", res.text)
