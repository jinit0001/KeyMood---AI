from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass
class JournalEntry:
    id: UUID
    user_id: UUID
    content: str
    ai_summary: str | None
    linked_emotion_prediction_id: UUID | None
    created_at: datetime
    updated_at: datetime
    tags: list[str] = field(default_factory=list)


class JournalRepository(Protocol):
    def add(self, entry: JournalEntry) -> None: ...
    def get_by_id(self, entry_id: UUID) -> JournalEntry | None: ...
    def update(self, entry: JournalEntry) -> None: ...
    def delete(self, entry_id: UUID) -> None: ...
    def list_for_user(self, user_id: UUID, limit: int, offset: int) -> list[JournalEntry]: ...
    def search(self, user_id: UUID, query: str | None, tag: str | None, limit: int, offset: int) -> list[JournalEntry]: ...
