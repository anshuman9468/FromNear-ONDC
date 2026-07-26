import asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.ondc.protocol.builders import ConfirmRequestBuilder

DATABASE_URL = "postgresql+asyncpg://postgres.tkwwwyoofrzrdckmnzcy:Anshuman%409311@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"

async def main():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(text("SELECT transaction_id, state, raw_response FROM orders WHERE transaction_id='6da7a6c5-8a7c-49b8-aac9-59767473a076'"))
        row = result.fetchone()
        if not row:
            print("Order not found")
            return
            
        transaction_id = row[0]
        raw_response = row[2]
        print("--- ON_INIT RAW RESPONSE ---")
        print(json.dumps(raw_response, indent=2))
        
        init_order = raw_response.get("message", {}).get("order", {})
        billing = init_order.get("billing", {})
        quote = init_order.get("quote", {})
        payment = init_order.get("payment", {})
        tags = init_order.get("tags", [])
        quote_amount = quote.get("price", {}).get("value", "200.00")
        order_id = init_order.get("id", "order-123")
        
        payload = ConfirmRequestBuilder.build(
            transaction_id=transaction_id,
            message_id="msg-123",
            bpp_id=raw_response.get("context", {}).get("bpp_id"),
            bpp_uri=raw_response.get("context", {}).get("bpp_uri"),
            provider_id="P1",
            items=init_order.get("items", []),
            billing_address={},
            shipping_address={},
            amount=quote_amount,
            order_id=order_id,
            quote=quote,
            payment=payment,
            tags=tags,
            created_at=billing.get("created_at", ""),
            updated_at=billing.get("updated_at", ""),
            fulfillments=init_order.get("fulfillments", []),
            billing=billing,
            provider=init_order.get("provider", {}),
        )
        
        print("\n--- GENERATED CONFIRM PAYLOAD ---")
        print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
