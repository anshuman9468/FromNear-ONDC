from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from app.models.search_cache import SearchCache
from app.repositories.base import BaseRepository


class SearchRepository(BaseRepository[SearchCache]):
    def __init__(self) -> None:
        super().__init__(SearchCache)

    async def save_items_async(
        self,
        db: AsyncSession,
        *,
        transaction_id: str,
        message_id: str,
        items: List[dict],
        raw_response: dict
    ) -> List[SearchCache]:
        """Save a list of parsed items from an on_search callback to the database cache."""
        db_objs = []
        for item in items:
            db_obj = SearchCache(
                transaction_id=transaction_id,
                message_id=message_id,
                provider_id=item.get("provider_id"),
                provider_name=item.get("provider_name"),
                item_id=item.get("item_id"),
                item_name=item.get("item_name"),
                price=item.get("price"),
                currency=item.get("currency", "INR"),
                raw_response=raw_response
            )
            db.add(db_obj)
            db_objs.append(db_obj)
        await db.commit()
        return db_objs

    async def get_by_transaction_id_async(
        self,
        db: AsyncSession,
        transaction_id: str
    ) -> List[SearchCache]:
        """Retrieve cached search results by transaction ID (async)."""
        result = await db.execute(
            select(self.model).filter(self.model.transaction_id == transaction_id)
        )
        return list(result.scalars().all())

    def get_by_transaction_id(
        self,
        db: Session,
        transaction_id: str
    ) -> List[SearchCache]:
        """Retrieve cached search results by transaction ID (sync)."""
        return db.query(self.model).filter(self.model.transaction_id == transaction_id).all()


search_repo = SearchRepository()
