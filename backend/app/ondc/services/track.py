import uuid
import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.ondc.client.http_client import ondc_http_client, safe_ondc_post
from app.repositories.order import order_repo
from app.ondc.protocol.builders import TrackRequestBuilder
from app.ondc.protocol.parsers import TrackResponse

logger = logging.getLogger(__name__)


class TrackService:
    async def initiate_track(
        self,
        db: AsyncSession,
        *,
        transaction_id: str,
    ) -> Dict[str, str]:
        """Build and send a standard ONDC /track request to the BPP."""
        message_id = str(uuid.uuid4())
        
        order = await order_repo.get_by_transaction_id_async(db, transaction_id)
        if not order:
            raise ValueError(f"Order not found for transaction_id={transaction_id}")
            
        bpp_id = order.raw_response.get("context", {}).get("bpp_id") if order.raw_response else None
        bpp_uri = order.raw_response.get("context", {}).get("bpp_uri") if order.raw_response else None
        
        if not bpp_id or not bpp_uri or not order.order_id:
            raise ValueError("Incomplete order state. Cannot track without order_id and BPP details.")
            
        payload = TrackRequestBuilder.build(
            transaction_id=transaction_id,
            message_id=message_id,
            bpp_id=bpp_id,
            bpp_uri=bpp_uri,
            order_id=order.order_id,
        )
        
        bpp_url = f"{bpp_uri.rstrip('/')}/track"
        logger.info(f"Sending /track request to BPP: {bpp_url}")
        
        return await safe_ondc_post(
            url=bpp_url,
            payload=payload,
            transaction_id=transaction_id,
            message_id=message_id,
            sign=True
        )

    async def handle_on_track(self, db: AsyncSession, payload: Dict[str, Any]) -> None:
        """Process incoming on_track callback, parsing tracking details."""
        try:
            parser = TrackResponse(payload)
            if not parser.is_success:
                logger.error(f"on_track callback reports error: {parser.error}")
                return
                
            transaction_id = parser.transaction_id
            if not transaction_id:
                logger.warning("Missing transaction_id in callback context")
                return
                
            order = await order_repo.get_by_transaction_id_async(db, transaction_id)
            if not order:
                logger.warning(f"Order not found for transaction_id={transaction_id} on_track callback")
                return
                
            order.raw_response = payload
            db.add(order)
            await db.commit()
            logger.info(f"Handled on_track for transaction_id={transaction_id}, url={parser.tracking_url}")
        except Exception as e:
            logger.error(f"Error handling on_track: {str(e)}", exc_info=True)


track_service = TrackService()
