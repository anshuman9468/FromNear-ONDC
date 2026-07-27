import logging
import asyncio
from app.ondc.bpp.client import bpp_client

logger = logging.getLogger(__name__)


class BppInitService:
    async def process_init(self, payload: dict):
        try:
            context = payload.get("context", {})
            message = payload.get("message", {})
            order = message.get("order", {})

            await asyncio.sleep(1)

            # Pass through items with fulfillment_ids intact
            items = order.get("items", [])
            for item in items:
                if "fulfillment_ids" not in item:
                    item["fulfillment_ids"] = ["F1"]

            response_message = {
                "order": {
                    "provider": order.get("provider", {"id": "P1"}),
                    "items": items,
                    "billing": order.get("billing", {}),
                    "fulfillments": order.get("fulfillments", []),
                    "quote": order.get("quote", {}),
                    "payment": {
                        "@ondc/org/buyer_app_finder_fee_type": order.get("payment", {}).get("@ondc/org/buyer_app_finder_fee_type", "percent"),
                        "@ondc/org/buyer_app_finder_fee_amount": order.get("payment", {}).get("@ondc/org/buyer_app_finder_fee_amount", "3"),
                        "@ondc/org/settlement_details": [
                            {
                                "settlement_counterparty": "seller-app",
                                "settlement_phase": "sale-amount",
                                "settlement_type": "neft",
                                "beneficiary_name": "FromNear Store",
                                "bank_name": "Mock Bank",
                                "branch_name": "MG Road",
                                "settlement_bank_account_no": "1234567890",
                                "settlement_ifsc_code": "MOCK0001234"
                            }
                        ]
                    }
                }
            }

            await bpp_client.send_callback(context, "on_init", response_message)
        except Exception as e:
            logger.error(f"ERROR in process_init: {e}", exc_info=True)

    async def handle_init(self, payload: dict):
        asyncio.create_task(self.process_init(payload))
        logger.info(f"Accepted /init for tx {payload.get('context', {}).get('transaction_id')}")


bpp_init_service = BppInitService()
