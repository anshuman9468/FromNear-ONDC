from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BppLifecycleState(Base):
    """Durable correlation state shared by BPP instances for one transaction."""

    __tablename__ = "bpp_lifecycle_states"

    transaction_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
