import uuid
import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.ondc.client.http_client import ondc_http_client, safe_ondc_post
from app.repositories.order import order_repo
from app.ondc.protocol.builders import CancelRequestBuilder
from app.ondc.protocol.parsers import CancelResponse

logger = logging.getLogger(__name__)


class CancelService:
    async def initiate_cancel(
        self,
        db: AsyncSession,
        *,
        transaction_id: str,
        cancellation_reason_id: str = "002",
    ) -> Dict[str, str]:
        """Build and send a standard ONDC /cancel request to the BPP."""
        message_id = str(uuid.uuid4())
        
        order = await order_repo.get_by_transaction_id_async(db, transaction_id)
        if not order:
            raise ValueError(f"Order not found for transaction_id={transaction_id}")
            
        bpp_id = order.raw_response.get("context", {}).get("bpp_id") if order.raw_response else None
        bpp_uri = order.raw_response.get("context", {}).get("bpp_uri") if order.raw_response else None
        
        if not bpp_id or not bpp_uri or not order.order_id:
            raise ValueError("Incomplete order state. Cannot cancel without order_id and BPP details.")
            
        payload = CancelRequestBuilder.build(
            transaction_id=transaction_id,
            message_id=message_id,
            bpp_id=bpp_id,
            bpp_uri=bpp_uri,
            order_id=order.order_id,
            cancellation_reason_id=cancellation_reason_id,
        )
        
        bpp_url = f"{bpp_uri.rstrip('/')}/cancel"
        logger.info(f"Sending /cancel request to BPP: {bpp_url}")
        
        return await safe_ondc_post(
            url=bpp_url,
            payload=payload,
            transaction_id=transaction_id,
            message_id=message_id,
            sign=True
        )

    async def handle_on_cancel(self, db: AsyncSession, payload: Dict[str, Any]) -> None:
        """Process incoming on_cancel callback, marking order state as CANCELLED."""
        parser = CancelResponse(payload)
        if not parser.is_success:
            logger.error(f"on_cancel callback reports error: {parser.error}")
            return
            
        transaction_id = parser.transaction_id
        if not transaction_id:
            raise ValueError("Missing transaction_id in callback context")
            
        order = await order_repo.get_by_transaction_id_async(db, transaction_id)
        if not order:
            logger.warning(f"Order not found for transaction_id={transaction_id} on_cancel callback")
            return
            
        order.state = "CANCELLED"
        order.raw_response = payload
        db.add(order)
        await db.commit()
        logger.info(f"Handled on_cancel for transaction_id={transaction_id}, state updated to CANCELLED")


# Singleton instance
cancel_service = CancelService()
