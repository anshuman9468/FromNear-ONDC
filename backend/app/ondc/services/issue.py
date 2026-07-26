import uuid
import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.ondc.client.http_client import safe_ondc_post
from app.repositories.order import order_repo
from app.ondc.protocol.builders import IssueRequestBuilder

logger = logging.getLogger(__name__)


class IssueService:
    async def initiate_issue(
        self,
        db: AsyncSession,
        *,
        transaction_id: str,
        issue_id: Optional[str] = None,
        short_desc: str = "Issue with item quality",
        long_desc: str = "Detailed issue with item quality",
    ) -> Dict[str, Any]:
        """Build and send an ONDC /issue request to the BPP."""
        message_id = str(uuid.uuid4())
        
        order = await order_repo.get_by_transaction_id_async(db, transaction_id)
        if not order:
            raise ValueError(f"Order not found for transaction_id={transaction_id}")
            
        bpp_id = order.raw_response.get("context", {}).get("bpp_id") if order.raw_response else None
        bpp_uri = order.raw_response.get("context", {}).get("bpp_uri") if order.raw_response else None
        
        if not bpp_id or not bpp_uri or not order.order_id:
            raise ValueError("Incomplete order state. Cannot raise issue without order_id and BPP details.")
            
        cached_order = order.raw_response.get("message", {}).get("order", {}) if order.raw_response else {}
        
        raw_items = cached_order.get("items", [])
        items_payload = []
        for it in raw_items:
            qty = it.get("quantity")
            count = qty.get("count", 1) if isinstance(qty, dict) else (qty if isinstance(qty, int) else 1)
            items_payload.append({
                "id": it.get("id", "I1"),
                "quantity": count
            })
        if not items_payload:
            items_payload = [{"id": "I1", "quantity": 1}]
            
        raw_fulfillments = cached_order.get("fulfillments", [])
        ful_payload = []
        for f in raw_fulfillments:
            st = f.get("state")
            code = st.get("descriptor", {}).get("code", "Order-delivered") if isinstance(st, dict) else (st if isinstance(st, str) else "Order-delivered")
            ful_payload.append({
                "id": f.get("id", "F1"),
                "state": code
            })
        if not ful_payload:
            ful_payload = [{"id": "F1", "state": "Order-delivered"}]
            
        order_details = {
            "id": order.order_id,
            "state": cached_order.get("state", "Completed"),
            "items": items_payload,
            "fulfillments": ful_payload,
            "provider_id": order.provider_id or "P1"
        }
            
        payload = IssueRequestBuilder.build(
            transaction_id=transaction_id,
            message_id=message_id,
            bpp_id=bpp_id,
            bpp_uri=bpp_uri,
            order_id=order.order_id,
            issue_id=issue_id,
            short_desc=short_desc,
            long_desc=long_desc,
            order_details=order_details,
        )
        
        bpp_url = f"{bpp_uri.rstrip('/')}/issue"
        logger.info(f"Sending /issue request to BPP: {bpp_url}")
        
        return await safe_ondc_post(
            url=bpp_url,
            payload=payload,
            transaction_id=transaction_id,
            message_id=message_id,
            sign=True
        )

    async def handle_on_issue(self, db: AsyncSession, payload: Dict[str, Any]) -> None:
        """Process incoming on_issue callback."""
        try:
            transaction_id = payload.get("context", {}).get("transaction_id")
            if not transaction_id:
                return
            order = await order_repo.get_by_transaction_id_async(db, transaction_id)
            if order:
                order.raw_response = payload
                db.add(order)
                await db.commit()
        except Exception as e:
            logger.error(f"Error handling on_issue: {str(e)}", exc_info=True)

    async def handle_on_issue_status(self, db: AsyncSession, payload: Dict[str, Any]) -> None:
        """Process incoming on_issue_status callback."""
        try:
            transaction_id = payload.get("context", {}).get("transaction_id")
            if not transaction_id:
                return
            order = await order_repo.get_by_transaction_id_async(db, transaction_id)
            if order:
                order.raw_response = payload
                db.add(order)
                await db.commit()
        except Exception as e:
            logger.error(f"Error handling on_issue_status: {str(e)}", exc_info=True)


issue_service = IssueService()
