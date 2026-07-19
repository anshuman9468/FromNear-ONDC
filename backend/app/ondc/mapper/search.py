from typing import Dict, Any, List
from app.ondc.schemas.product import ProductModel


class SearchMapper:
    @staticmethod
    def map_on_search_to_products(payload: Dict[str, Any]) -> List[ProductModel]:
        """Map ONDC on_search catalog structure to list of internal ProductModel objects."""
        products = []
        context = payload.get("context", {})
        transaction_id = context.get("transaction_id", "")
        bpp_id = context.get("bpp_id", "")
        bpp_uri = context.get("bpp_uri", "")
        
        message = payload.get("message", {})
        catalog = message.get("catalog", {})
        
        # ONDC v1.2.0 uses 'bpp/providers'
        providers = catalog.get("bpp/providers", [])
        if not providers:
            # Fallback check if it is wrapped in an alternate field
            providers = catalog.get("providers", [])
            
        for provider in providers:
            provider_id = provider.get("id", "unknown_provider")
            provider_desc = provider.get("descriptor", {})
            provider_name = provider_desc.get("name", "Unknown Store")
            
            items = provider.get("items", [])
            for item in items:
                item_id = item.get("id", "unknown_item")
                item_desc = item.get("descriptor", {})
                item_name = item_desc.get("name", "Unknown Product")
                item_desc_text = item_desc.get("short_desc") or item_desc.get("long_desc") or ""
                
                # Normalize images to a flat list of strings
                raw_images = item_desc.get("images", [])
                images = []
                if isinstance(raw_images, list):
                    for img in raw_images:
                        if isinstance(img, str):
                            images.append(img)
                        elif isinstance(img, dict) and "url" in img:
                            images.append(img["url"])
                elif isinstance(raw_images, str):
                    images = [raw_images]
                    
                price_data = item.get("price", {})
                currency = price_data.get("currency", "INR")
                try:
                    price_val = float(price_data.get("value", 0.0))
                except (ValueError, TypeError):
                    price_val = 0.0
                    
                product = ProductModel(
                    id=item_id,
                    name=item_name,
                    description=item_desc_text,
                    price=price_val,
                    currency=currency,
                    images=images,
                    provider_id=provider_id,
                    provider_name=provider_name,
                    bpp_id=bpp_id,
                    bpp_uri=bpp_uri,
                    transaction_id=transaction_id
                )
                products.append(product)
                
        return products
