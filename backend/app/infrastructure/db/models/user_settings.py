import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class UserSettingsModel(Base):
    """Not in DATABASE.md — see app/domain/profile/entities.py docstring
    for why this table was gap-filled and how. JSONB columns follow the
    same convention DATABASE.md already uses for flexible structured
    data (companion_memory.value, recommendations.payload, etc.)."""

    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    privacy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notifications: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ai_preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
