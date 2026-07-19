import uuid
import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.ondc.client.http_client import ondc_http_client, safe_ondc_post
from app.repositories.order import order_repo, address_repo
from app.models.order import Address
from app.ondc.protocol.builders import InitRequestBuilder
from app.ondc.protocol.parsers import InitResponse

logger = logging.getLogger(__name__)


class InitService:
    async def initiate_init(
        self,
        db: AsyncSession,
        *,
        transaction_id: str,
        billing_address: Dict[str, Any],
        shipping_address: Dict[str, Any],
        user_id: int,
    ) -> Dict[str, str]:
        """Build and send a standard ONDC /init request to the BPP."""
        message_id = str(uuid.uuid4())
        
        order = await order_repo.get_by_transaction_id_async(db, transaction_id)
        if not order:
            raise ValueError(f"Order not found for transaction_id={transaction_id}")
            
        # Parse items from DB to build request payload
        items = [{"id": item.item_id, "quantity": item.quantity} for item in order.items]
        
        # Save Address to DB for the user if it doesn't exist
        # Check if we should save the shipping address as user address
        address_obj = Address(
            user_id=user_id,
            name=shipping_address.get("name", "Unknown"),
            phone=shipping_address.get("phone", ""),
            house=shipping_address.get("house", ""),
            street=shipping_address.get("street", ""),
            city=shipping_address.get("city", ""),
            state=shipping_address.get("state", ""),
            pincode=shipping_address.get("pincode", ""),
        )
        db.add(address_obj)
        await db.commit()
        
        # Look up BPP credentials from cached response
        bpp_id = order.raw_response.get("context", {}).get("bpp_id") if order.raw_response else None
        bpp_uri = order.raw_response.get("context", {}).get("bpp_uri") if order.raw_response else None
        
        if not bpp_id or not bpp_uri:
            raise ValueError("BPP credentials (bpp_id/bpp_uri) not found in order cache. Execute select flow first.")
            
        payload = InitRequestBuilder.build(
            transaction_id=transaction_id,
            message_id=message_id,
            bpp_id=bpp_id,
            bpp_uri=bpp_uri,
            provider_id=order.provider_id,
            items=items,
            billing_address=billing_address,
            shipping_address=shipping_address,
        )
        
        bpp_url = f"{bpp_uri.rstrip('/')}/init"
        logger.info(f"Sending /init request to BPP: {bpp_url}")
        
        return await safe_ondc_post(
            url=bpp_url,
            payload=payload,
            transaction_id=transaction_id,
            message_id=message_id,
            sign=True
        )

    async def handle_on_init(self, db: AsyncSession, payload: Dict[str, Any]) -> None:
        """Process incoming on_init callback, updating order status to INITIALIZED."""
        parser = InitResponse(payload)
        if not parser.is_success:
            logger.error(f"on_init callback reports error: {parser.error}")
            return
            
        transaction_id = parser.transaction_id
        if not transaction_id:
            raise ValueError("Missing transaction_id in callback context")
            
        order = await order_repo.get_by_transaction_id_async(db, transaction_id)
        if not order:
            logger.warning(f"Order not found for transaction_id={transaction_id} on_init callback")
            return
            
        order.amount = parser.quote_price
        order.raw_response = payload
        order.state = "INITIALIZED"
        
        db.add(order)
        await db.commit()
        logger.info(f"Handled on_init for transaction_id={transaction_id}, new amount={order.amount}")


init_service = InitService()
