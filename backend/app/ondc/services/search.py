import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.settings import settings
from app.ondc.client.http_client import ondc_http_client, safe_ondc_post
from app.repositories.search import search_repo
from app.ondc.mapper.search import SearchMapper
from app.ondc.schemas.product import ProductModel

logger = logging.getLogger(__name__)


from app.ondc.protocol.builders import SearchRequestBuilder

class OndcSearchService:
    async def initiate_search(
        self,
        query: str = "",
        *,
        transaction_id: Optional[str] = None,
        bpp_id: Optional[str] = None,
        bpp_uri: Optional[str] = None,
        mode: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build and send an ONDC search payload to Gateway or specific BPP."""
        txn_id = transaction_id or str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        
        payload = SearchRequestBuilder.build(
            query=query,
            transaction_id=txn_id,
            message_id=message_id,
            bpp_id=bpp_id,
            bpp_uri=bpp_uri,
            mode=mode,
            start_time=start_time,
            end_time=end_time,
        )
        
        if bpp_uri:
            target_url = f"{bpp_uri.rstrip('/')}/search"
        else:
            target_url = f"{settings.ONDC_GATEWAY_URL.rstrip('/')}/search"
            
        logger.info(f"Sending search request (mode={mode}) to {target_url}")
        
        return await safe_ondc_post(
            url=target_url,
            payload=payload,
            transaction_id=txn_id,
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
                    "currency": price_data.get("currency", "INR"),
                    "location_id": str(item.get("location_id") or item.get("location") or ""),
                    "parent_item_id": str(item.get("parent_item_id") or ""),
                    "fulfillment_id": str(item.get("fulfillment_id") or ""),
                    "tags": item.get("tags") if isinstance(item.get("tags"), list) else [],
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
            
            location_id = ""
            parent_item_id = ""
            fulfillment_id = ""
            tags = []
            raw_providers = []
            try:
                # Safely extract images and description from raw response JSON
                raw_catalog = record.raw_response.get("message", {}).get("catalog", {})
                raw_providers = raw_catalog.get("bpp/providers", []) or raw_catalog.get("providers", [])
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
                                location_id = str(item.get("location_id") or item.get("location") or "")
                                parent_item_id = str(item.get("parent_item_id") or "")
                                fulfillment_id = str(item.get("fulfillment_id") or "")
                                tags = item.get("tags") if isinstance(item.get("tags"), list) else []
            except Exception:
                pass

            # Keep identity available even when a descriptor has no images or
            # the raw response uses an alternate catalog provider key.
            if not location_id or not parent_item_id or not fulfillment_id:
                for provider in raw_providers:
                    if provider.get("id") != record.provider_id:
                        continue
                    for item in provider.get("items", []):
                        if item.get("id") == record.item_id:
                            location_id = location_id or str(item.get("location_id") or item.get("location") or "")
                            parent_item_id = parent_item_id or str(item.get("parent_item_id") or "")
                            fulfillment_id = fulfillment_id or str(item.get("fulfillment_id") or "")
                            tags = tags or (item.get("tags") if isinstance(item.get("tags"), list) else [])
                            break
                
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
                transaction_id=record.transaction_id,
                location_id=location_id or "",
                parent_item_id=parent_item_id or "",
                fulfillment_id=fulfillment_id or "",
                tags=tags,
            )
            products.append(product)
            
        return products

    async def enrich_items_for_selection(
        self,
        db: AsyncSession,
        transaction_id: str,
        provider_id: str,
        items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Attach canonical identity from the cached on_search catalog.

        The UI may submit only an item id and quantity. The catalog response
        for the same transaction is the authority for location, parent, and
        fulfillment references used in the subsequent /select request.
        """
        records = await search_repo.get_by_transaction_id_async(db, transaction_id)
        catalog_items: Dict[str, Dict[str, Any]] = {}
        for record in records:
            if record.provider_id != provider_id or not record.item_id:
                continue
            raw_catalog = (record.raw_response or {}).get("message", {}).get("catalog", {})
            raw_providers = raw_catalog.get("bpp/providers", []) or raw_catalog.get("providers", [])
            for provider in raw_providers:
                if provider.get("id") != provider_id:
                    continue
                for catalog_item in provider.get("items", []):
                    if catalog_item.get("id") == record.item_id:
                        catalog_items[record.item_id] = catalog_item
                        break

        enriched = []
        for item in items:
            current = dict(item) if isinstance(item, dict) else {}
            catalog_item = catalog_items.get(str(current.get("id")))
            if catalog_item:
                current["catalog_item"] = catalog_item
            enriched.append(current)
        return enriched


ondc_search_service = OndcSearchService()
