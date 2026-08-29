import logging
import asyncio
from app.ondc.bpp.client import bpp_client
from app.ondc.bpp.order_builder import _now
from app.ondc.bpp.state_machine import lifecycle_tracker
from app.ondc.bpp.lifecycle import is_prepaid_track_flow, push_prepaid_post_track_statuses

logger = logging.getLogger(__name__)


class BppTrackService:
    async def process_track(self, payload: dict):
        context = payload.get("context", {})
        message = payload.get("message", {})
        transaction_id = context.get("transaction_id", "default_tx")
        stored_order = lifecycle_tracker.get_stored_order(transaction_id) or message.get("order", {})

        await asyncio.sleep(0.5)

        order_id = message.get("order_id") or stored_order.get("id") or lifecycle_tracker.get_order_id(transaction_id) or "2026-07-27-1001"
        created_at = lifecycle_tracker.get_created_at(transaction_id) or stored_order.get("created_at") or _now()

        response_message = {
            "tracking": {
                "id": f"TRK-{order_id}",
                "url": "https://ondc.fromnear.com/tracking/mock",
                "status": "active",
            }
        }
        await bpp_client.send_callback(context, "on_track", response_message)
        lifecycle_tracker.record_callback(transaction_id, "on_track", "active")

        # Every /track flow needs the final delivery statuses.  The endpoint
        # itself proves this is a tracking scenario; relying on a global mode
        # incorrectly omitted them for ordinary prepaid flows.
        await push_prepaid_post_track_statuses(
            context=context,
            payload=payload,
            order_id=order_id,
            created_at=created_at,
            stored_order=stored_order,
        )

    async def handle_track(self, payload: dict):
        await self.process_track(payload)
        logger.info(f"Accepted /track for tx {payload.get('context', {}).get('transaction_id')}")


bpp_track_service = BppTrackService()
