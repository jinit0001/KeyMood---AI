from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.exceptions import JournalEntryNotFoundError, ValidationError
from app.domain.journal import JournalEntry, JournalRepository

MAX_CONTENT_LENGTH = 10_000


class JournalService:
    def __init__(self, repo: JournalRepository):
        self._repo = repo

    def create(self, user_id: UUID, content: str, tags: list[str] | None = None,
               linked_emotion_prediction_id: UUID | None = None) -> JournalEntry:
        self._validate(content)
        now = datetime.now(timezone.utc)
        entry = JournalEntry(id=uuid4(), user_id=user_id, content=content, ai_summary=None,
                              linked_emotion_prediction_id=linked_emotion_prediction_id,
                              created_at=now, updated_at=now, tags=tags or [])
        self._repo.add(entry)
        return entry

    def get(self, user_id: UUID, entry_id: UUID) -> JournalEntry:
        entry = self._repo.get_by_id(entry_id)
        if entry is None or entry.user_id != user_id:
            raise JournalEntryNotFoundError()
        return entry

    def update(self, user_id: UUID, entry_id: UUID, content: str | None = None, tags: list[str] | None = None) -> JournalEntry:
        entry = self.get(user_id, entry_id)
        if content is not None:
            self._validate(content)
            entry.content = content
        if tags is not None:
            entry.tags = tags
        entry.updated_at = datetime.now(timezone.utc)
        self._repo.update(entry)
        return entry

    def delete(self, user_id: UUID, entry_id: UUID) -> None:
        entry = self.get(user_id, entry_id)
        self._repo.delete(entry.id)

    def list_entries(self, user_id: UUID, limit: int = 20, offset: int = 0) -> list[JournalEntry]:
        return self._repo.list_for_user(user_id, min(max(limit, 1), 100), offset)

    def search(self, user_id: UUID, query: str | None, tag: str | None, limit: int = 20, offset: int = 0) -> list[JournalEntry]:
        return self._repo.search(user_id, query, tag, min(max(limit, 1), 100), offset)

    def request_summary(self, user_id: UUID, entry_id: UUID) -> JournalEntry:
        """202-style async job shape — no real LLM wired up yet, ai_summary stays None."""
        return self.get(user_id, entry_id)

    def _validate(self, content: str) -> None:
        if not content.strip():
            raise ValidationError("Journal content cannot be empty.")
        if len(content) > MAX_CONTENT_LENGTH:
            raise ValidationError(f"Journal content must be at most {MAX_CONTENT_LENGTH} characters.")
