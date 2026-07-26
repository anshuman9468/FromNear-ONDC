import asyncio
from app.ondc.services.search import ondc_search_service
from app.core.settings import settings
import uuid
import httpx
from app.ondc.client.http_client import generate_auth_header
from datetime import datetime, timezone

async def test_search():
    query = "shoes" # or something else, it might return all
    transaction_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    context = ondc_search_service.generate_context("search", transaction_id, message_id)
    
    payload = {
        "context": context,
        "message": {
            "intent": {
                "item": {
                    "descriptor": {
                        "name": query
                    }
                },
                "fulfillment": {
                    "type": "Delivery"
                }
            }
        }
    }
    
    import json
    body_bytes = json.dumps(payload).encode("utf-8")
    auth_header = generate_auth_header(body_bytes)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": auth_header
    }
    
    print(f"Sending search to mock seller with transaction_id: {transaction_id}")
    async with httpx.AsyncClient() as client:
        res = await client.post("https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/seller/search", content=body_bytes, headers=headers)
        print("Status:", res.status_code)
        print("Response:", res.text)

if __name__ == "__main__":
    asyncio.run(test_search())
