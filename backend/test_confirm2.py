import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from app.models.order import Order
from app.ondc.protocol.builders import ConfirmRequestBuilder
import json

async def main():
    engine = create_async_engine("postgresql+asyncpg://postgres.tkwwwyoofrzrdckmnzcy:Anshuman%409311@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres")
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        result = await session.execute(select(Order).where(Order.transaction_id == "c98fea97-1ce2-41ac-8894-210f43dbc187"))
        order = result.scalar_one_or_none()
        
        if order:
            init_order = order.raw_response.get("message", {}).get("order", {})
            quote = init_order.get("quote", {})
            payment = init_order.get("payment", {})
            tags = init_order.get("tags", [])
            billing = init_order.get("billing", {})
            
            payload = ConfirmRequestBuilder.build(
                transaction_id=order.transaction_id,
                message_id="test-msg-id",
                bpp_id="bpp1",
                bpp_uri="http://bpp",
                provider_id=order.provider_id,
                items=[{"id": "I1", "quantity": 1}],
                billing_address={},
                shipping_address={},
                amount=quote.get("price", {}).get("value", "0.0"),
                order_id="order-123",
                quote=quote,
                payment=payment,
                tags=tags,
                billing=billing,
                created_at=billing.get("created_at", ""),
                updated_at=billing.get("updated_at", ""),
                fulfillments=init_order.get("fulfillments", []),
                provider=init_order.get("provider", {})
            )
            print(json.dumps(payload, indent=2))
            
asyncio.run(main())
