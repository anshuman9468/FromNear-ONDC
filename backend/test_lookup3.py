import requests
import json
print("V1 lookup preprod:")
try:
    r = requests.post("https://preprod.registry.ondc.org/lookup", json={"subscriber_id": "ondc.fromnear.com", "type": "BAP"})
    print(r.status_code, r.text)
except Exception as e: print(e)
print("V1 lookup staging:")
try:
    r = requests.post("https://staging.registry.ondc.org/lookup", json={"subscriber_id": "ondc.fromnear.com", "type": "BAP"})
    print(r.status_code, r.text)
except Exception as e: print(e)
