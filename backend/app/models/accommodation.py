import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class AccommodationLedgerEvent(Base):
    __tablename__ = "accommodation_ledger_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    action: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    message_id: Mapped[str] = mapped_column(String(255), index=True, nullable=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
