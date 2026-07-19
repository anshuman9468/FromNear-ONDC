from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload
from app.models.order import Order, OrderItem, Address
from app.repositories.base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    def __init__(self) -> None:
        super().__init__(Order)

    async def get_by_transaction_id_async(self, db: AsyncSession, transaction_id: str) -> Optional[Order]:
        """Fetch order by transaction ID with items loaded."""
        result = await db.execute(
            select(self.model)
            .filter(self.model.transaction_id == transaction_id)
            .options(selectinload(self.model.items))
        )
        return result.scalars().first()

    async def get_by_order_id_async(self, db: AsyncSession, order_id: str) -> Optional[Order]:
        """Fetch order by ONDC order ID with items loaded."""
        result = await db.execute(
            select(self.model)
            .filter(self.model.order_id == order_id)
            .options(selectinload(self.model.items))
        )
        return result.scalars().first()

    async def get_multi_orders_async(self, db: AsyncSession, *, skip: int = 0, limit: int = 100) -> List[Order]:
        """Fetch multiple orders with items preloaded."""
        result = await db.execute(
            select(self.model)
            .options(selectinload(self.model.items))
            .offset(skip)
            .limit(limit)
            .order_by(self.model.created_at.desc())
        )
        return list(result.scalars().all())


class OrderItemRepository(BaseRepository[OrderItem]):
    def __init__(self) -> None:
        super().__init__(OrderItem)

    async def get_by_order_id_async(self, db: AsyncSession, order_id: int) -> List[OrderItem]:
        result = await db.execute(
            select(self.model).filter(self.model.order_id == order_id)
        )
        return list(result.scalars().all())


class AddressRepository(BaseRepository[Address]):
    def __init__(self) -> None:
        super().__init__(Address)

    async def get_by_user_id_async(self, db: AsyncSession, user_id: int) -> List[Address]:
        result = await db.execute(
            select(self.model).filter(self.model.user_id == user_id)
        )
        return list(result.scalars().all())


order_repo = OrderRepository()
order_item_repo = OrderItemRepository()
address_repo = AddressRepository()
