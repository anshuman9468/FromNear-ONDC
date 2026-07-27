import logging
import asyncio
from app.ondc.bpp.client import bpp_client

logger = logging.getLogger(__name__)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class BppUpdateService:
    async def process_update(self, payload: dict):
        try:
            context = payload.get("context", {})
            message = payload.get("message", {})
            order = message.get("order", {})

            await asyncio.sleep(1)

            order_id = order.get("id", "mock-order-id")

            # Determine update type from update_target
            update_target = message.get("update_target", "fulfillment")

            items = order.get("items", [])
            for item in items:
                if "fulfillment_ids" not in item:
                    item["fulfillment_ids"] = ["F1"]

            # Reflect the update back (return/partial-return accepted)
            fulfillments = order.get("fulfillments", [])
            if not fulfillments:
                fulfillments = [
                    {
                        "id": "F1",
                        "type": "Delivery",
                        "@ondc/org/provider_name": "FromNear Delivery",
                        "tracking": False,
                        "@ondc/org/category": "Standard Delivery",
                        "@ondc/org/TAT": "PT45M",
                        "state": {"descriptor": {"code": "Return-Initiated"}}
                    }
                ]
            else:
                for f in fulfillments:
                    if "state" not in f:
                        f["state"] = {"descriptor": {"code": "Return-Initiated"}}

            response_message = {
                "order": {
                    "id": order_id,
                    "state": "In-progress",
                    "provider": order.get("provider", {"id": "P1"}),
                    "items": items,
                    "billing": order.get("billing", {}),
                    "fulfillments": fulfillments,
                    "quote": order.get("quote", {}),
                    "payment": order.get("payment", {}),
                    "updated_at": _now()
                }
            }

            await bpp_client.send_callback(context, "on_update", response_message)

            # Steps 15-16: send 2 more unsolicited on_update status pushes
            await self._send_return_lifecycle(context, order_id, order, items, fulfillments)

        except Exception as e:
            logger.error(f"ERROR in process_update: {e}", exc_info=True)

    async def _send_return_lifecycle(self, context, order_id, order, items, fulfillments):
        """Send unsolicited on_update updates for return lifecycle (steps 15-16)."""
        return_states = [
            ("Return-Picked", 5),     # Step 15
            ("Return-Delivered", 5),  # Step 16
        ]

        for state_code, delay in return_states:
            await asyncio.sleep(delay)
            try:
                updated_fulfillments = []
                for f in fulfillments:
                    fc = f.copy()
                    fc["state"] = {"descriptor": {"code": state_code}}
                    updated_fulfillments.append(fc)

                update_message = {
                    "order": {
                        "id": order_id,
                        "state": "In-progress",
                        "provider": order.get("provider", {"id": "P1"}),
                        "items": items,
                        "billing": order.get("billing", {}),
                        "fulfillments": updated_fulfillments,
                        "quote": order.get("quote", {}),
                        "payment": order.get("payment", {}),
                        "updated_at": _now()
                    }
                }
                await bpp_client.send_callback(context, "on_update", update_message)
                logger.info(f"Sent unsolicited on_update: {state_code} for order {order_id}")
            except Exception as e:
                logger.error(f"ERROR sending on_update {state_code}: {e}", exc_info=True)

    async def handle_update(self, payload: dict):
        asyncio.create_task(self.process_update(payload))
        logger.info(f"Accepted /update for tx {payload.get('context', {}).get('transaction_id')}")


bpp_update_service = BppUpdateService()
