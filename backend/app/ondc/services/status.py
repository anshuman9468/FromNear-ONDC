import uuid
import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.ondc.client.http_client import ondc_http_client, safe_ondc_post
from app.repositories.order import order_repo
from app.ondc.protocol.builders import StatusRequestBuilder
from app.ondc.protocol.parsers import StatusResponse

logger = logging.getLogger(__name__)


class StatusService:
    async def initiate_status(
        self,
        db: AsyncSession,
        *,
        transaction_id: str,
    ) -> Dict[str, str]:
        """Build and send a standard ONDC /status request to the BPP."""
        message_id = str(uuid.uuid4())
        
        order = await order_repo.get_by_transaction_id_async(db, transaction_id)
        if not order:
            raise ValueError(f"Order not found for transaction_id={transaction_id}")
            
        bpp_id = order.raw_response.get("context", {}).get("bpp_id") if order.raw_response else None
        bpp_uri = order.raw_response.get("context", {}).get("bpp_uri") if order.raw_response else None
        
        if not bpp_id or not bpp_uri or not order.order_id:
            raise ValueError("Incomplete order state. Cannot request status without order_id and BPP details.")
            
        payload = StatusRequestBuilder.build(
            transaction_id=transaction_id,
            message_id=message_id,
            bpp_id=bpp_id,
            bpp_uri=bpp_uri,
            order_id=order.order_id,
        )
        
        bpp_url = f"{bpp_uri.rstrip('/')}/status"
        logger.info(f"Sending /status request to BPP: {bpp_url}")
        
        return await safe_ondc_post(
            url=bpp_url,
            payload=payload,
            transaction_id=transaction_id,
            message_id=message_id,
            sign=True
        )

    async def handle_on_status(self, db: AsyncSession, payload: Dict[str, Any]) -> None:
        """Process incoming on_status callback, updating order state in DB."""
        try:
            parser = StatusResponse(payload)
            if not parser.is_success:
                logger.error(f"on_status callback reports error: {parser.error}")
                return
                
            transaction_id = parser.transaction_id
            if not transaction_id:
                logger.warning("Missing transaction_id in callback context")
                return
                
            order = await order_repo.get_by_transaction_id_async(db, transaction_id)
            if not order:
                logger.warning(f"Order not found for transaction_id={transaction_id} on_status callback")
                return
                
            new_state = parser.state
            if new_state:
                order.state = new_state
                
            order.raw_response = payload
            db.add(order)
            await db.commit()
            logger.info(f"Handled on_status for transaction_id={transaction_id}, new state={order.state}")
        except Exception as e:
            logger.error(f"Error handling on_status: {str(e)}", exc_info=True)


status_service = StatusService()
