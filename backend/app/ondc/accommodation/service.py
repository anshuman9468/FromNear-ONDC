import logging
import uuid
from typing import Any, Dict, Optional

from app.ondc.accommodation.builders import AccommodationRequestBuilder
from app.ondc.accommodation.profile import get_accommodation_buyer_profile
from app.ondc.client.http_client import safe_ondc_post
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.accommodation import AccommodationLedgerEvent
from app.database.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class AccommodationBuyerService:
    def __init__(self):
        self.profile = get_accommodation_buyer_profile()
        self.builder = AccommodationRequestBuilder(self.profile)

    async def initiate_search(
        self,
        *,
        location: Optional[str] = None,
        check_in: Optional[str] = None,
        check_out: Optional[str] = None,
        guests: Optional[int] = None,
        rooms: Optional[int] = None,
        city: Optional[str] = None,
        transaction_id: Optional[str] = None,
        message_id: Optional[str] = None,
        bpp_id: Optional[str] = None,
        bpp_uri: Optional[str] = None,
        tags: Optional[list[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        txn_id = transaction_id or str(uuid.uuid4())
        message_id = message_id or str(uuid.uuid4())
        payload = self.builder.search(
            transaction_id=txn_id,
            message_id=message_id,
            location=location,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            rooms=rooms,
            city=city,
            bpp_id=bpp_id,
            bpp_uri=bpp_uri,
            tags=tags,
        )
        return await self._post(payload, txn_id, message_id, bpp_uri, "search")

    async def send_order_action(
        self,
        *,
        action: str,
        transaction_id: str,
        bpp_id: str,
        bpp_uri: str,
        order: Dict[str, Any],
    ) -> Dict[str, Any]:
        message_id = str(uuid.uuid4())
        order = dict(order)
        order.setdefault("id", "order-1")
        payload = self.builder.action_with_order(
            action=action,
            transaction_id=transaction_id,
            message_id=message_id,
            bpp_id=bpp_id,
            bpp_uri=bpp_uri,
            order=order,
        )
        return await self._post(payload, transaction_id, message_id, bpp_uri, action)

    async def send_order_id_action(
        self,
        *,
        action: str,
        transaction_id: str,
        bpp_id: str,
        bpp_uri: str,
        order_id: str,
        extra_message: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        message_id = str(uuid.uuid4())
        payload = self.builder.action_with_order_id(
            action=action,
            transaction_id=transaction_id,
            message_id=message_id,
            bpp_id=bpp_id,
            bpp_uri=bpp_uri,
            order_id=order_id,
            extra_message=extra_message,
        )
        return await self._post(payload, transaction_id, message_id, bpp_uri, action)

    async def handle_callback(self, payload: Dict[str, Any], db: Optional[AsyncSession] = None) -> None:
        context = payload.get("context", {})
        logger.info(
            "Accommodation callback received: action=%s transaction_id=%s message_id=%s",
            context.get("action"),
            context.get("transaction_id"),
            context.get("message_id"),
        )
        if db is not None:
            message = payload.get("message", {})
            order = message.get("order", {}) if isinstance(message, dict) else {}
            quote = order.get("quote", {}) if isinstance(order, dict) else {}
            price = quote.get("price", {}).get("value") if isinstance(quote, dict) else None
            try:
                amount = float(price) if price is not None else None
            except (TypeError, ValueError):
                amount = None
            db.add(AccommodationLedgerEvent(
                action=context.get("action", "callback"), direction="inbound",
                transaction_id=context.get("transaction_id", "unknown"),
                message_id=context.get("message_id"), order_id=order.get("id"),
                state=(order.get("state", {}).get("descriptor", {}).get("code")
                       if isinstance(order, dict) else None), amount=amount, payload=payload,
            ))
            await db.commit()

    async def _post(
        self,
        payload: Dict[str, Any],
        transaction_id: str,
        message_id: str,
        bpp_uri: Optional[str],
        action: str,
    ) -> Dict[str, Any]:
        target_base = bpp_uri.rstrip("/") if bpp_uri else self.profile.gateway_url.rstrip("/")
        target_url = f"{target_base}/{action}"
        logger.info("Sending accommodation /%s request to %s", action, target_url)
        async with AsyncSessionLocal() as db:
            db.add(AccommodationLedgerEvent(
                action=action, direction="outbound", transaction_id=transaction_id,
                message_id=message_id, order_id=payload.get("message", {}).get("order", {}).get("id"),
                payload=payload,
            ))
            await db.commit()
        return await safe_ondc_post(
            url=target_url, payload=payload, transaction_id=transaction_id,
            message_id=message_id, sign=True,
            subscriber_id=self.profile.subscriber_id,
            unique_key_id=self.profile.unique_key_id,
            private_key_str=self.profile.signing_private_key,
        )


accommodation_buyer_service = AccommodationBuyerService()
