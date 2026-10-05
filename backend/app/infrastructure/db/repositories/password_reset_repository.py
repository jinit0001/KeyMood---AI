from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.auth.entities import PasswordReset
from app.infrastructure.db.models.password_reset import PasswordResetModel


def _to_domain(row: PasswordResetModel) -> PasswordReset:
    return PasswordReset(
        id=row.id,
        user_id=row.user_id,
        token_hash=row.token_hash,
        expires_at=row.expires_at,
        consumed_at=row.consumed_at,
        created_at=row.created_at,
    )


class SqlPasswordResetRepository:
    """Implements domain.auth.repositories.PasswordResetRepository."""

    def __init__(self, session: Session):
        self._session = session

    def add(self, record: PasswordReset) -> None:
        row = PasswordResetModel(
            id=record.id,
            user_id=record.user_id,
            token_hash=record.token_hash,
            expires_at=record.expires_at,
            consumed_at=record.consumed_at,
        )
        self._session.add(row)
        self._session.flush()

    def get_by_token_hash(self, token_hash: str) -> PasswordReset | None:
        stmt = select(PasswordResetModel).where(PasswordResetModel.token_hash == token_hash)
        row = self._session.execute(stmt).scalar_one_or_none()
        return _to_domain(row) if row else None

    def mark_consumed(self, record_id: UUID, consumed_at: datetime) -> None:
        row = self._session.get(PasswordResetModel, record_id)
        if row is None:
            raise ValueError(f"PasswordReset {record_id} not found")
        row.consumed_at = consumed_at
        self._session.flush()
