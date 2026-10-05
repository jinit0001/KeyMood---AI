from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.infrastructure.db.base import Base
from app.services.companion import ChatMessage, ChatSession


class ChatSessionModel(Base):
    __tablename__ = "companion_sessions"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ChatMessageModel(Base):
    __tablename__ = "companion_messages"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("companion_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    flagged_crisis: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def _to_session(m: ChatSessionModel) -> ChatSession:
    return ChatSession(id=m.id, user_id=m.user_id, created_at=m.created_at)


def _to_message(m: ChatMessageModel) -> ChatMessage:
    return ChatMessage(id=m.id, session_id=m.session_id, role=m.role, content=m.content, flagged_crisis=m.flagged_crisis, created_at=m.created_at)


class SqlChatSessionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_or_create(self, user_id: UUID) -> ChatSession:
        row = self._db.execute(select(ChatSessionModel).where(ChatSessionModel.user_id == user_id)).scalar_one_or_none()
        if row is None:
            row = ChatSessionModel(user_id=user_id)
            self._db.add(row)
            self._db.flush()
        return _to_session(row)

    def get(self, session_id: UUID) -> ChatSession | None:
        row = self._db.get(ChatSessionModel, session_id)
        return _to_session(row) if row else None


class SqlChatMessageRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, session_id: UUID, role: str, content: str, flagged_crisis: bool) -> ChatMessage:
        row = ChatMessageModel(session_id=session_id, role=role, content=content, flagged_crisis=flagged_crisis)
        self._db.add(row)
        self._db.flush()
        return _to_message(row)

    def list_for_session(self, session_id: UUID, limit: int = 50) -> list[ChatMessage]:
        rows = self._db.execute(
            select(ChatMessageModel)
            .where(ChatMessageModel.session_id == session_id)
            .order_by(ChatMessageModel.created_at.asc())
            .limit(limit)
        ).scalars().all()
        return [_to_message(r) for r in rows]
