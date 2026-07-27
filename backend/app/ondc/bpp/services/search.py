import json
import logging
import asyncio
from pathlib import Path
from app.ondc.bpp.client import bpp_client

logger = logging.getLogger(__name__)

class BppSearchService:
    def __init__(self):
        # Load the mock catalog from the JSON file
        catalog_path = Path(__file__).parent.parent / "catalog" / "mock_catalog.json"
        with open(catalog_path, "r") as f:
            self.mock_catalog = json.load(f)

    async def process_search(self, payload: dict):
        """Asynchronously process the incoming search request and send on_search."""
        context = payload.get("context", {})
        
        # Simulate processing time
        await asyncio.sleep(1)
        
        # For a real BPP, we would parse payload["message"]["intent"] and filter our database.
        # Since this is a mock BPP for testing, we just return the full mock catalog.
        
        message = {
            "catalog": self.mock_catalog
        }
        
        # Send the on_search callback to the BAP
        await bpp_client.send_callback(context, "on_search", message)

    async def handle_search(self, payload: dict):
        """Handle the incoming /search request from a BAP or Gateway."""
        # Validate the incoming payload if needed, then trigger async processing
        # We don't block the HTTP response on the callback.
        asyncio.create_task(self.process_search(payload))
        logger.info(f"Accepted /search request for transaction {payload.get('context', {}).get('transaction_id')}")

bpp_search_service = BppSearchService()
