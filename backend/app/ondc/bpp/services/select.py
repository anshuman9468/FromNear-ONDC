import logging
import asyncio
from app.ondc.bpp.client import bpp_client
from app.ondc.bpp.order_builder import build_canonical_order, validate_ret10_payload
from app.ondc.bpp.state_machine import lifecycle_tracker
from app.ondc.bpp.lifecycle import is_out_of_stock_flow, is_rto_flow

logger = logging.getLogger(__name__)


class BppSelectService:
    async def process_select(self, payload: dict):
        context = payload.get("context", {})
        transaction_id = context.get("transaction_id", "default_tx")
        select_count = lifecycle_tracker.increment_select(transaction_id)

        # Workbench carries the merchant-side RTO marker on /select, while
        # later /init and /confirm payloads may omit it. Persist it now so
        # callback scheduling remains tied to the actual flow.
        if is_rto_flow(context, payload):
            lifecycle_tracker.mark_rto_flow(transaction_id)

        await asyncio.sleep(0.5)

        incoming_items = payload.get("message", {}).get("order", {}).get("items", [])
        is_oos = is_out_of_stock_flow(transaction_id)
        if not is_oos and incoming_items:
            from app.ondc.bpp.order_builder import _get_catalog_item_map
            catalog_map = _get_catalog_item_map()
            for it in incoming_items:
                it_id = it.get("id")
                cat_it = catalog_map.get(it_id)
                req_qty = int(it.get("quantity", {}).get("selected", {}).get("count") or it.get("quantity", {}).get("count", 1))
                avail_qty = int((cat_it or {}).get("quantity", {}).get("available", {}).get("count", 99))
                if req_qty > avail_qty or (cat_it and avail_qty == 0):
                    is_oos = True
                    break

        order_obj = build_canonical_order(
            action="on_select",
            payload=payload,
            state_code="Non-serviceable" if is_oos or select_count >= 2 else "Serviceable",
        )

        # Out-of-stock flow: Workbench expects an ONDC domain error at callback root
        if is_oos or select_count >= 2:
            lifecycle_tracker.mark_out_of_stock_flow(transaction_id)
            for item in order_obj.get("items", []):
                item.get("quantity", {}).setdefault("selected", {})["count"] = 0

            lifecycle_tracker.store_order(
                transaction_id,
                order_obj,
                context,
                order_obj.get("created_at") or context.get("timestamp"),
                order_obj.get("id", "pending"),
            )
            await bpp_client.send_callback_error(
                context,
                "on_select",
                {
                    "type": "DOMAIN-ERROR",
                    "code": "40002",
                    "message": "Item quantity unavailable",
                },
                {"order": order_obj},
            )
            return

        response_message = {"order": order_obj}
        response_payload = {
            "context": bpp_client._create_response_context(context, "on_select"),
            "message": response_message,
        }

        errors = validate_ret10_payload("on_select", response_payload)
        if errors:
            logger.error(f"RET10 Validation Failed for on_select: {errors}")
            raise ValueError(f"RET10 Schema Error: {errors}")

        lifecycle_tracker.store_order(
            transaction_id,
            order_obj,
            context,
            order_obj.get("created_at") or context.get("timestamp"),
            order_obj.get("id", "pending"),
        )
        await bpp_client.send_callback(context, "on_select", response_message)

    async def handle_select(self, payload: dict):
        await self.process_select(payload)
        logger.info(f"Accepted /select for tx {payload.get('context', {}).get('transaction_id')}")


bpp_select_service = BppSelectService()
