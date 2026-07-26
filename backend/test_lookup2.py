import requests
import json

def test_lookup(registry_url):
    print(f"Testing {registry_url}...")
    try:
        response = requests.post(f"{registry_url}/lookup", json={
            "subscriber_id": "ondc.fromnear.com",
            "type": "BAP",
            "domain": "nic2004:52110"
        })
        print(response.status_code)
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))
        else:
            print(response.text)
    except Exception as e:
        print(e)

test_lookup("https://preprod.registry.ondc.org/ondc")
test_lookup("https://staging.registry.ondc.org/ondc")
