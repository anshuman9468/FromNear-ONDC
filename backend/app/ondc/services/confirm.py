import uuid
import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.ondc.client.http_client import ondc_http_client, safe_ondc_post
from app.repositories.order import order_repo
from app.ondc.protocol.builders import ConfirmRequestBuilder
from app.ondc.protocol.parsers import ConfirmResponse

logger = logging.getLogger(__name__)


class ConfirmService:
    async def initiate_confirm(
        self,
        db: AsyncSession,
        *,
        transaction_id: str,
    ) -> Dict[str, str]:
        """Build and send a standard ONDC /confirm request to the BPP."""
        message_id = str(uuid.uuid4())
        
        order = await order_repo.get_by_transaction_id_async(db, transaction_id)
        if not order:
            raise ValueError(f"Order not found for transaction_id={transaction_id}")
            
        items = [{"id": item.item_id, "quantity": item.quantity} for item in order.items]
        
        # Load shipping/billing address details from cached on_init payload
        if not order.raw_response:
            raise ValueError("No previous ONDC workflow data cached on order. Execute init first.")
            
        init_order = order.raw_response.get("message", {}).get("order", {})
        billing = init_order.get("billing", {})
        billing_address = {
            "name": billing.get("name", ""),
            "phone": billing.get("phone", ""),
            "house": billing.get("address", {}).get("door", ""),
            "street": billing.get("address", {}).get("street", ""),
            "city": billing.get("address", {}).get("city", ""),
            "state": billing.get("address", {}).get("state", ""),
            "pincode": billing.get("address", {}).get("area_code", ""),
        }
        
        fulfillment = init_order.get("fulfillments", [{}])[0]
        end_contact = fulfillment.get("end", {}).get("contact", {})
        end_location = fulfillment.get("end", {}).get("location", {})
        shipping_address = {
            "name": end_contact.get("name", ""),
            "phone": end_contact.get("phone", ""),
            "house": end_location.get("address", {}).get("door", ""),
            "street": end_location.get("address", {}).get("street", ""),
            "city": end_location.get("address", {}).get("city", ""),
            "state": end_location.get("address", {}).get("state", ""),
            "pincode": end_location.get("address", {}).get("area_code", ""),
        }
        
        bpp_id = order.raw_response.get("context", {}).get("bpp_id")
        bpp_uri = order.raw_response.get("context", {}).get("bpp_uri")
        
        if not bpp_id or not bpp_uri:
            raise ValueError("BPP credentials (bpp_id/bpp_uri) not found in order cache.")
            
        payload = ConfirmRequestBuilder.build(
            transaction_id=transaction_id,
            message_id=message_id,
            bpp_id=bpp_id,
            bpp_uri=bpp_uri,
            provider_id=order.provider_id,
            items=items,
            billing_address=billing_address,
            shipping_address=shipping_address,
            amount=order.amount,
        )
        
        bpp_url = f"{bpp_uri.rstrip('/')}/confirm"
        logger.info(f"Sending /confirm request to BPP: {bpp_url}")
        
        return await safe_ondc_post(
            url=bpp_url,
            payload=payload,
            transaction_id=transaction_id,
            message_id=message_id,
            sign=True
        )

    async def handle_on_confirm(self, db: AsyncSession, payload: Dict[str, Any]) -> None:
        """Process incoming on_confirm callback, completing order transaction."""
        parser = ConfirmResponse(payload)
        if not parser.is_success:
            logger.error(f"on_confirm callback reports error: {parser.error}")
            return
            
        transaction_id = parser.transaction_id
        if not transaction_id:
            raise ValueError("Missing transaction_id in callback context")
            
        order = await order_repo.get_by_transaction_id_async(db, transaction_id)
        if not order:
            logger.warning(f"Order not found for transaction_id={transaction_id} on_confirm callback")
            return
            
        order.order_id = parser.order_id
        order.raw_response = payload
        order.state = "CONFIRMED"
        
        db.add(order)
        await db.commit()
        logger.info(f"Handled on_confirm for transaction_id={transaction_id}, ONDC order_id={order.order_id}")


confirm_service = ConfirmService()
