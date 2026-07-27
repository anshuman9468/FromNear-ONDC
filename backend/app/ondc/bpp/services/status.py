import logging
import asyncio
from app.ondc.bpp.client import bpp_client

logger = logging.getLogger(__name__)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class BppStatusService:
    async def process_status(self, payload: dict):
        try:
            context = payload.get("context", {})
            message = payload.get("message", {})
            order_id = message.get("order_id", "mock-order-id")

            await asyncio.sleep(1)

            response_message = {
                "order": {
                    "id": order_id,
                    "state": "In-progress",
                    "provider": {"id": "P1"},
                    "items": [
                        {"id": "I1", "fulfillment_ids": ["F1"], "quantity": {"selected": {"count": 1}}},
                        {"id": "I2", "fulfillment_ids": ["F1"], "quantity": {"selected": {"count": 1}}}
                    ],
                    "fulfillments": [
                        {
                            "id": "F1",
                            "type": "Delivery",
                            "@ondc/org/provider_name": "FromNear Delivery",
                            "tracking": False,
                            "@ondc/org/category": "Standard Delivery",
                            "@ondc/org/TAT": "PT45M",
                            "state": {"descriptor": {"code": "Return-Initiated"}}
                        }
                    ],
                    "updated_at": _now()
                }
            }

            await bpp_client.send_callback(context, "on_status", response_message)
        except Exception as e:
            logger.error(f"ERROR in process_status: {e}", exc_info=True)

    async def handle_status(self, payload: dict):
        asyncio.create_task(self.process_status(payload))
        logger.info(f"Accepted /status for tx {payload.get('context', {}).get('transaction_id')}")


bpp_status_service = BppStatusService()
