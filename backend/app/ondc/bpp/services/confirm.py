import logging
import asyncio
import uuid
from datetime import datetime, timezone
from app.ondc.bpp.client import bpp_client

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class BppConfirmService:
    async def process_confirm(self, payload: dict):
        try:
            context = payload.get("context", {})
            message = payload.get("message", {})
            order = message.get("order", {})

            await asyncio.sleep(1)

            order_id = order.get("id") or str(uuid.uuid4())
            created_at = _now()

            # Ensure items have fulfillment_ids
            items = order.get("items", [])
            for item in items:
                if "fulfillment_ids" not in item:
                    item["fulfillment_ids"] = ["F1"]

            # Build fulfillments with Packed state (order accepted, ready to pack)
            fulfillments = order.get("fulfillments", [])
            for f in fulfillments:
                if "state" not in f:
                    f["state"] = {"descriptor": {"code": "Packed"}}

            response_message = {
                "order": {
                    "id": order_id,
                    "state": "Accepted",
                    "provider": order.get("provider", {"id": "P1"}),
                    "items": items,
                    "billing": order.get("billing", {}),
                    "fulfillments": fulfillments if fulfillments else [
                        {
                            "id": "F1",
                            "type": "Delivery",
                            "@ondc/org/provider_name": "FromNear Delivery",
                            "tracking": False,
                            "@ondc/org/category": "Standard Delivery",
                            "@ondc/org/TAT": "PT45M",
                            "state": {"descriptor": {"code": "Packed"}}
                        }
                    ],
                    "quote": order.get("quote", {}),
                    "payment": order.get("payment", {}),
                    "created_at": created_at,
                    "updated_at": created_at
                }
            }

            await bpp_client.send_callback(context, "on_confirm", response_message)

            # After confirmation, fire the order-lifecycle on_status updates (steps 7-12)
            # These are UNSOLICITED status pushes through the fulfillment lifecycle
            await self._send_order_lifecycle(context, order_id, order)

        except Exception as e:
            logger.error(f"ERROR in process_confirm: {e}", exc_info=True)

    async def _send_order_lifecycle(self, context: dict, order_id: str, order: dict):
        """Send unsolicited on_status updates to simulate order lifecycle."""
        lifecycle_states = [
            ("Order-picked-up", 3),    # Step 7
            ("Out-for-delivery", 5),   # Step 8
            ("Order-delivered", 5),    # Step 9
            ("Return-Initiated", 3),   # Step 10
            ("Return-Picked", 5),      # Step 11
            ("Return-Delivered", 5),   # Step 12
        ]

        items = order.get("items", [])
        for item in items:
            if "fulfillment_ids" not in item:
                item["fulfillment_ids"] = ["F1"]

        for state_code, delay in lifecycle_states:
            await asyncio.sleep(delay)
            try:
                updated_at = _now()
                status_message = {
                    "order": {
                        "id": order_id,
                        "state": "In-progress" if state_code not in ("Order-delivered", "Return-Delivered") else "Completed",
                        "provider": order.get("provider", {"id": "P1"}),
                        "items": items,
                        "billing": order.get("billing", {}),
                        "fulfillments": [
                            {
                                "id": "F1",
                                "type": "Delivery",
                                "@ondc/org/provider_name": "FromNear Delivery",
                                "tracking": False,
                                "@ondc/org/category": "Standard Delivery",
                                "@ondc/org/TAT": "PT45M",
                                "state": {"descriptor": {"code": state_code}}
                            }
                        ],
                        "quote": order.get("quote", {}),
                        "payment": order.get("payment", {}),
                        "updated_at": updated_at
                    }
                }
                await bpp_client.send_callback(context, "on_status", status_message)
                logger.info(f"Sent unsolicited on_status: {state_code} for order {order_id}")
            except Exception as e:
                logger.error(f"ERROR sending on_status {state_code}: {e}", exc_info=True)

    async def handle_confirm(self, payload: dict):
        asyncio.create_task(self.process_confirm(payload))
        logger.info(f"Accepted /confirm for tx {payload.get('context', {}).get('transaction_id')}")


bpp_confirm_service = BppConfirmService()
