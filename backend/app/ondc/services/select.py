import copy
import uuid
import logging
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.ondc.client.http_client import ondc_http_client, safe_ondc_post
from app.repositories.order import order_repo, order_item_repo
from app.models.order import Order, OrderItem
from app.ondc.protocol.builders import SelectRequestBuilder
from app.ondc.protocol.parsers import SelectResponse
from app.ondc.services.search import ondc_search_service

logger = logging.getLogger(__name__)


def _merge_on_select_with_request(
    callback_payload: Dict[str, Any],
    request_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Keep canonical select references when an on_select omits them.

    BPP callbacks may return only the fields needed to update the quote. The
    subsequent /init request still needs the identifiers selected from the
    catalog, so callback item fields are layered over the original request
    item fields by item id. No identifier is synthesized here.
    """
    merged = copy.deepcopy(callback_payload)
    callback_order = merged.setdefault("message", {}).setdefault("order", {})
    request_order = (request_payload or {}).get("message", {}).get("order", {})
    request_items = request_order.get("items", []) if isinstance(request_order, dict) else []
    callback_items = callback_order.get("items", [])

    request_by_id = {
        item.get("id"): item
        for item in request_items
        if isinstance(item, dict) and item.get("id")
    }
    if isinstance(callback_items, list) and callback_items:
        preserved_items = []
        for callback_item in callback_items:
            if not isinstance(callback_item, dict):
                continue
            item_id = callback_item.get("id")
            preserved = copy.deepcopy(request_by_id.get(item_id, {}))
            preserved.update(copy.deepcopy(callback_item))
            preserved_items.append(preserved)
        callback_order["items"] = preserved_items
    elif request_items:
        callback_order["items"] = copy.deepcopy(request_items)

    return merged


class SelectService:
    async def initiate_select(
        self,
        db: AsyncSession,
        *,
        transaction_id: str,
        bpp_id: str,
        bpp_uri: str,
        provider_id: str,
        provider_name: str,
        items: List[Dict[str, Any]],
        user_id: int,
    ) -> Dict[str, str]:
        """Build and send a standard ONDC /select request to the BPP."""
        message_id = str(uuid.uuid4())
        
        # Resolve references from the on_search catalog before serializing.
        # This keeps the request independent of UI aliases and preserves the
        # actual parent-child relationship for every selected item.
        resolved_items = await ondc_search_service.enrich_items_for_selection(
            db, transaction_id, provider_id, items
        )

        # Build request body
        payload = SelectRequestBuilder.build(
            transaction_id=transaction_id,
            message_id=message_id,
            bpp_id=bpp_id,
            bpp_uri=bpp_uri,
            provider_id=provider_id,
            items=resolved_items
        )
        
        # Check if Order already exists, if not, create one
        order = await order_repo.get_by_transaction_id_async(db, transaction_id)
        if not order:
            order = Order(
                user_id=user_id,
                transaction_id=transaction_id,
                message_id=message_id,
                provider_id=provider_id,
                provider_name=provider_name,
                state="SELECTED",
                amount=0.0,
                currency="INR",
            )
            
            # Keep the canonical select request available until on_select and
            # init complete the lifecycle state.
            order.raw_response = payload
            db.add(order)
            await db.commit()
            await db.refresh(order)
            
            # Save items
            for item in resolved_items:
                quantity = item.get("quantity", 1)
                if isinstance(quantity, dict):
                    quantity = quantity.get("count") or quantity.get("selected", {}).get("count") or 1
                order_item = OrderItem(
                    order_id=order.id,
                    item_id=item["id"],
                    item_name=item.get("name", "Unknown"),
                    quantity=int(quantity),
                    price=item.get("price", 0.0)
                )
                db.add(order_item)
            await db.commit()
            
        bpp_url = f"{bpp_uri.rstrip('/')}/select"
        logger.info(f"Sending /select request to BPP: {bpp_url}")
        
        return await safe_ondc_post(
            url=bpp_url,
            payload=payload,
            transaction_id=transaction_id,
            message_id=message_id,
            sign=True
        )

    async def handle_on_select(self, db: AsyncSession, payload: Dict[str, Any]) -> None:
        """Process incoming on_select callback, updating quotes and items."""
        try:
            parser = SelectResponse(payload)
            transaction_id = parser.transaction_id or payload.get("context", {}).get("transaction_id")
            if not transaction_id:
                logger.warning("Missing transaction_id in callback context")
                return
                
            order = await order_repo.get_by_transaction_id_async(db, transaction_id)
            if not order:
                logger.warning(f"Order not found for transaction_id={transaction_id} on_select callback")
                return
                
            # Preserve the original select item references while taking the
            # callback context and quote data as the current response.
            order.raw_response = _merge_on_select_with_request(payload, order.raw_response or {})

            if not parser.is_success:
                logger.warning(f"on_select callback reports error: {parser.error}")
                order.state = "SELECT_ERROR"
                db.add(order)
                await db.commit()
                return
                
            # Update order amount and save raw_response
            order.amount = parser.quote_price
            order.state = "SELECTED"
            
            quote_items = parser.items
            for qi in quote_items:
                item_id = qi.get("id")
                for local_item in order.items:
                    if local_item.item_id == item_id:
                        price_val = qi.get("price", {}).get("value")
                        if price_val:
                            local_item.price = float(price_val)
                            
            db.add(order)
            await db.commit()
            logger.info(f"Handled on_select for transaction_id={transaction_id}, new amount={order.amount}")
        except Exception as e:
            logger.error(f"Error handling on_select: {str(e)}", exc_info=True)


select_service = SelectService()
