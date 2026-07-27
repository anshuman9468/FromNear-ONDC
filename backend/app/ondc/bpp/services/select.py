import logging
import asyncio
from app.ondc.bpp.client import bpp_client

logger = logging.getLogger(__name__)


class BppSelectService:
    async def process_select(self, payload: dict):
        try:
            context = payload.get("context", {})
            message = payload.get("message", {})

            await asyncio.sleep(1)

            order = message.get("order", {})
            items = order.get("items", [])

            # Load catalog for price lookup
            from app.ondc.bpp.services.search import bpp_search_service
            catalog_items = bpp_search_service.mock_catalog.get("bpp/providers", [])[0].get("items", [])
            item_map = {item["id"]: item for item in catalog_items}

            quote_breakup = []
            total_value = 0.0
            response_items = []

            for item in items:
                item_id = item.get("id")
                quantity = item.get("quantity", {}).get("count", 1)

                catalog_item = item_map.get(item_id)
                if catalog_item:
                    price = float(catalog_item["price"]["value"])
                    item_total = price * quantity
                    total_value += item_total
                    max_count = catalog_item.get("quantity", {}).get("maximum", {}).get("count", 5)
                    avail_count = catalog_item.get("quantity", {}).get("available", {}).get("count", 100)

                    # Each item MUST have fulfillment_ids (required by ONDC validation)
                    response_items.append({
                        "id": item_id,
                        "fulfillment_ids": ["F1"],
                        "location_ids": ["L1"],
                        "quantity": {"selected": {"count": quantity}},
                    })

                    # Breakup entry MUST have item.quantity.maximum.count
                    quote_breakup.append({
                        "@ondc/org/item_id": item_id,
                        "@ondc/org/item_quantity": {"count": quantity},
                        "title": catalog_item["descriptor"]["name"],
                        "@ondc/org/title_type": "item",
                        "price": {"currency": "INR", "value": f"{item_total:.2f}"},
                        "item": {
                            "price": {"currency": "INR", "value": f"{price:.2f}"},
                            "quantity": {
                                "available": {"count": str(avail_count)},
                                "maximum": {"count": str(max_count)}
                            }
                        }
                    })

            # Delivery charges
            delivery_charge = 50.0
            total_value += delivery_charge
            quote_breakup.append({
                "@ondc/org/item_id": "F1",
                "title": "Delivery charges",
                "@ondc/org/title_type": "delivery",
                "price": {"currency": "INR", "value": f"{delivery_charge:.2f}"}
            })

            response_message = {
                "order": {
                    "provider": {"id": "P1", "locations": [{"id": "L1"}]},
                    "items": response_items,
                    "fulfillments": [
                        {
                            "id": "F1",
                            "@ondc/org/provider_name": "FromNear Delivery",
                            "tracking": False,
                            "type": "Delivery",
                            "@ondc/org/category": "Standard Delivery",
                            "@ondc/org/TAT": "PT45M",
                            "state": {"descriptor": {"code": "Serviceable"}}
                        }
                    ],
                    "quote": {
                        "price": {"currency": "INR", "value": f"{total_value:.2f}"},
                        "breakup": quote_breakup,
                        "ttl": "PT15M"
                    }
                }
            }

            await bpp_client.send_callback(context, "on_select", response_message)
        except Exception as e:
            logger.error(f"ERROR in process_select: {e}", exc_info=True)

    async def handle_select(self, payload: dict):
        asyncio.create_task(self.process_select(payload))
        logger.info(f"Accepted /select for tx {payload.get('context', {}).get('transaction_id')}")


bpp_select_service = BppSelectService()
