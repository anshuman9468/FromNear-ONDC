from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from app.models.user import User
from app.repositories.base import BaseRepository
from app.schemas.user import UserCreate, UserUpdate
from app.utils.security import hash_password


class UserRepository(BaseRepository[User]):
    def __init__(self) -> None:
        super().__init__(User)

    # --- Sync Operations ---
    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        return db.query(self.model).filter(self.model.email == email).first()

    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        db_obj = User(
            email=obj_in.email,
            hashed_password=hash_password(obj_in.password),
            full_name=obj_in.full_name,
            is_superuser=obj_in.is_superuser,
            is_active=obj_in.is_active,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self, db: Session, *, db_obj: User, obj_in: UserUpdate
    ) -> User:
        update_data = obj_in.model_dump(exclude_unset=True)
        if "password" in update_data and update_data["password"]:
            update_data["hashed_password"] = hash_password(update_data["password"])
            del update_data["password"]
        return super().update(db, db_obj=db_obj, obj_in=update_data)

    # --- Async Operations ---
    async def get_by_email_async(
        self, db: AsyncSession, email: str
    ) -> Optional[User]:
        result = await db.execute(
            select(self.model).filter(self.model.email == email)
        )
        return result.scalars().first()

    async def create_async(
        self, db: AsyncSession, *, obj_in: UserCreate
    ) -> User:
        db_obj = User(
            email=obj_in.email,
            hashed_password=hash_password(obj_in.password),
            full_name=obj_in.full_name,
            is_superuser=obj_in.is_superuser,
            is_active=obj_in.is_active,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update_async(
        self, db: AsyncSession, *, db_obj: User, obj_in: UserUpdate
    ) -> User:
        update_data = obj_in.model_dump(exclude_unset=True)
        if "password" in update_data and update_data["password"]:
            update_data["hashed_password"] = hash_password(update_data["password"])
            del update_data["password"]
        return await super().update_async(db, db_obj=db_obj, obj_in=update_data)


user_repo = UserRepository()
