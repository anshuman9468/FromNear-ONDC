import asyncio
from app.ondc.bpp.services.select import bpp_select_service

payload = {
    "context": {
        "bap_uri": "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/buyer",
        "action": "select"
    },
    "message": {
        "order": {
            "items": [
                {"id": "I1", "location": "L1", "quantity": {"count": 1}},
                {"id": "I2", "location": "L1", "quantity": {"count": 1}}
            ]
        }
    }
}

import logging
logging.basicConfig(level=logging.INFO)

async def run():
    await bpp_select_service.process_select(payload)
    print("Done!")

if __name__ == "__main__":
    asyncio.run(run())
