import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models.order import Order
from app.core.settings import settings

engine = create_async_engine(settings.ASYNC_DATABASE_URI, echo=False)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def patch():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).filter(Order.transaction_id == "415951db-ea51-40be-bd3f-7e8c0d5cb4f7"))
        order = result.scalars().first()
        if order:
            order.raw_response = {
                "context": {
                    "bpp_id": "workbench.ondc.tech",
                    "bpp_uri": "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/seller"
                }
            }
            db.add(order)
            await db.commit()
            print("Patched successfully!")
        else:
            print("Order not found")

if __name__ == "__main__":
    asyncio.run(patch())
