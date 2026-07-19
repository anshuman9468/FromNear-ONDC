from typing import Generator, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from app.core.database import engine, SessionLocal, async_engine, AsyncSessionLocal


def get_db() -> Generator[Session, None, None]:
    """Sync database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Async database session dependency."""
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()
