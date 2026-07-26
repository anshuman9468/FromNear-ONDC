import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from app.models.order import Order
import json

async def main():
    engine = create_async_engine("postgresql+asyncpg://postgres.tkwwwyoofrzrdckmnzcy:Anshuman%409311@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres")
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        result = await session.execute(select(Order).where(Order.transaction_id == "c98fea97-1ce2-41ac-8894-210f43dbc187"))
        order = result.scalar_one_or_none()
        if order:
            print(json.dumps(order.raw_response, indent=2))
            
asyncio.run(main())
