from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domain.auth.entities import RefreshToken
from app.infrastructure.db.models.refresh_token import RefreshTokenModel


def _to_domain(row: RefreshTokenModel) -> RefreshToken:
    return RefreshToken(
        id=row.id,
        user_id=row.user_id,
        token_hash=row.token_hash,
        jti=row.jti,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
    )


class SqlRefreshTokenRepository:
    """Implements domain.auth.repositories.RefreshTokenRepository."""

    def __init__(self, session: Session):
        self._session = session

    def add(self, token: RefreshToken) -> None:
        row = RefreshTokenModel(
            id=token.id,
            user_id=token.user_id,
            token_hash=token.token_hash,
            jti=token.jti,
            expires_at=token.expires_at,
            revoked_at=token.revoked_at,
        )
        self._session.add(row)
        self._session.flush()

    def get_by_jti(self, jti: UUID) -> RefreshToken | None:
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.jti == jti)
        row = self._session.execute(stmt).scalar_one_or_none()
        return _to_domain(row) if row else None

    def revoke(self, token_id: UUID, revoked_at: datetime) -> None:
        row = self._session.get(RefreshTokenModel, token_id)
        if row is None:
            raise ValueError(f"RefreshToken {token_id} not found")
        row.revoked_at = revoked_at
        self._session.flush()

    def revoke_all_for_user(self, user_id: UUID, revoked_at: datetime) -> None:
        stmt = (
            update(RefreshTokenModel)
            .where(RefreshTokenModel.user_id == user_id, RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
        self._session.execute(stmt)
        self._session.flush()
