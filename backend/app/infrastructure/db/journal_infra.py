import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, delete, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session as DbSession, mapped_column

from app.domain.journal import JournalEntry
from app.infrastructure.db.base import Base


class JournalEntryModel(Base):
    __tablename__ = "journal_entries"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_emotion_prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emotion_predictions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class JournalTagModel(Base):
    __tablename__ = "journal_tags"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=False)
    tag: Mapped[str] = mapped_column(String(40), nullable=False)


class SqlJournalRepository:
    def __init__(self, db: DbSession): self._db = db

    def _to_domain(self, row: JournalEntryModel) -> JournalEntry:
        tags = self._db.execute(select(JournalTagModel.tag).where(JournalTagModel.entry_id == row.id)).scalars().all()
        return JournalEntry(id=row.id, user_id=row.user_id, content=row.content, ai_summary=row.ai_summary,
                             linked_emotion_prediction_id=row.linked_emotion_prediction_id,
                             created_at=row.created_at, updated_at=row.updated_at, tags=list(tags))

    def _sync_tags(self, entry_id, tags: list[str]) -> None:
        self._db.execute(delete(JournalTagModel).where(JournalTagModel.entry_id == entry_id))
        for tag in tags:
            self._db.add(JournalTagModel(id=uuid.uuid4(), entry_id=entry_id, tag=tag))

    def add(self, entry: JournalEntry) -> None:
        self._db.add(JournalEntryModel(id=entry.id, user_id=entry.user_id, content=entry.content,
                                        ai_summary=entry.ai_summary,
                                        linked_emotion_prediction_id=entry.linked_emotion_prediction_id))
        self._sync_tags(entry.id, entry.tags)
        self._db.flush()

    def get_by_id(self, entry_id) -> JournalEntry | None:
        row = self._db.get(JournalEntryModel, entry_id)
        return self._to_domain(row) if row else None

    def update(self, entry: JournalEntry) -> None:
        row = self._db.get(JournalEntryModel, entry.id)
        row.content, row.ai_summary = entry.content, entry.ai_summary
        self._sync_tags(entry.id, entry.tags)
        self._db.flush()

    def delete(self, entry_id) -> None:
        self._db.execute(delete(JournalTagModel).where(JournalTagModel.entry_id == entry_id))
        row = self._db.get(JournalEntryModel, entry_id)
        if row:
            self._db.delete(row)
        self._db.flush()

    def list_for_user(self, user_id, limit, offset) -> list[JournalEntry]:
        stmt = select(JournalEntryModel).where(JournalEntryModel.user_id == user_id).order_by(
            JournalEntryModel.created_at.desc()).limit(limit).offset(offset)
        return [self._to_domain(r) for r in self._db.execute(stmt).scalars().all()]

    def search(self, user_id, query, tag, limit, offset) -> list[JournalEntry]:
        stmt = select(JournalEntryModel).where(JournalEntryModel.user_id == user_id)
        if query:
            tsv = func.to_tsvector("english", JournalEntryModel.content)
            tsq = func.plainto_tsquery("english", query)
            stmt = stmt.where(tsv.op("@@")(tsq))
        if tag:
            stmt = stmt.join(JournalTagModel, JournalTagModel.entry_id == JournalEntryModel.id).where(JournalTagModel.tag == tag)
        stmt = stmt.order_by(JournalEntryModel.created_at.desc()).limit(limit).offset(offset)
        return [self._to_domain(r) for r in self._db.execute(stmt).scalars().all()]
