import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.settings import settings
from app.ondc.client.http_client import ondc_http_client, safe_ondc_post
from app.repositories.search import search_repo
from app.ondc.mapper.search import SearchMapper
from app.ondc.schemas.product import ProductModel

logger = logging.getLogger(__name__)


class OndcSearchService:
    @staticmethod
    def generate_context(action: str, transaction_id: str, message_id: str) -> Dict[str, Any]:
        """Generate a compliant ONDC request context."""
        return {
            "domain": settings.ONDC_DOMAIN,
            "country": settings.ONDC_COUNTRY,
            "city": settings.ONDC_CITY,
            "action": action,
            "core_version": "1.2.0",
            "bap_id": settings.ONDC_SUBSCRIBER_ID,
            "bap_uri": settings.ONDC_SUBSCRIBER_URI,
            "transaction_id": transaction_id,
            "message_id": message_id,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "ttl": "PT30S"
        }

    async def initiate_search(self, query: str) -> Dict[str, str]:
        """Build and broadcast a standard ONDC search payload to the configured Gateway."""
        transaction_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        
        context = self.generate_context("search", transaction_id, message_id)
        
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
        
        gateway_url = f"{settings.ONDC_GATEWAY_URL.rstrip('/')}/search"
        logger.info(f"Broadcasting search query='{query}' to Gateway: {gateway_url}")
        
        return await safe_ondc_post(
            url=gateway_url,
            payload=payload,
            transaction_id=transaction_id,
            message_id=message_id,
            sign=True
        )

    async def handle_on_search(self, db: AsyncSession, payload: Dict[str, Any]) -> None:
        """Process incoming on_search callback, parsing items and persisting them to cache."""
        context = payload.get("context", {})
        transaction_id = context.get("transaction_id")
        message_id = context.get("message_id")
        
        if not transaction_id or not message_id:
            raise ValueError("Invalid callback payload: context must contain transaction_id and message_id")
            
        message = payload.get("message", {})
        catalog = message.get("catalog", {})
        providers = catalog.get("bpp/providers", [])
        if not providers:
            providers = catalog.get("providers", [])
            
        flat_items = []
        for provider in providers:
            provider_id = provider.get("id", "unknown_provider")
            provider_name = provider.get("descriptor", {}).get("name", "Unknown Store")
            
            items = provider.get("items", [])
            for item in items:
                price_data = item.get("price", {})
                flat_items.append({
                    "provider_id": provider_id,
                    "provider_name": provider_name,
                    "item_id": item.get("id"),
                    "item_name": item.get("descriptor", {}).get("name", "Unknown Item"),
                    "price": float(price_data.get("value", 0.0)),
                    "currency": price_data.get("currency", "INR")
                })
                
        if flat_items:
            await search_repo.save_items_async(
                db=db,
                transaction_id=transaction_id,
                message_id=message_id,
                items=flat_items,
                raw_response=payload
            )
            logger.info(f"Cached {len(flat_items)} catalog items for transaction_id={transaction_id}")
        else:
            logger.warning(f"No catalog items parsed from on_search callback for transaction_id={transaction_id}")

    async def get_results(self, db: AsyncSession, transaction_id: str) -> List[ProductModel]:
        """Fetch cached products by transaction ID and map them to internal ProductModels."""
        cached_records = await search_repo.get_by_transaction_id_async(db, transaction_id)
        
        products = []
        for record in cached_records:
            # Reconstruct the ProductModel from cached flat fields and raw_response payload
            images = []
            description = ""
            
            try:
                # Safely extract images and description from raw response JSON
                raw_providers = record.raw_response.get("message", {}).get("catalog", {}).get("bpp/providers", [])
                for prov in raw_providers:
                    if prov.get("id") == record.provider_id:
                        for item in prov.get("items", []):
                            if item.get("id") == record.item_id:
                                desc_data = item.get("descriptor", {})
                                description = desc_data.get("short_desc") or desc_data.get("long_desc") or ""
                                raw_images = desc_data.get("images", [])
                                if isinstance(raw_images, list):
                                    images = [img if isinstance(img, str) else img.get("url", "") for img in raw_images]
                                elif isinstance(raw_images, str):
                                    images = [raw_images]
            except Exception:
                pass
                
            product = ProductModel(
                id=record.item_id or "",
                name=record.item_name or "",
                description=description,
                price=record.price or 0.0,
                currency=record.currency or "INR",
                images=images,
                provider_id=record.provider_id or "",
                provider_name=record.provider_name or "",
                bpp_id=record.raw_response.get("context", {}).get("bpp_id", ""),
                bpp_uri=record.raw_response.get("context", {}).get("bpp_uri", ""),
                transaction_id=record.transaction_id
            )
            products.append(product)
            
        return products


ondc_search_service = OndcSearchService()
