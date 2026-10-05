from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.auth.entities import OAuthIdentity
from app.infrastructure.db.models.oauth_identity import OAuthIdentityModel


def _to_domain(row: OAuthIdentityModel) -> OAuthIdentity:
    return OAuthIdentity(
        id=row.id,
        user_id=row.user_id,
        provider=row.provider,
        provider_user_id=row.provider_user_id,
        created_at=row.created_at,
    )


class SqlOAuthIdentityRepository:
    """Implements domain.auth.repositories.OAuthIdentityRepository."""

    def __init__(self, session: Session):
        self._session = session

    def get_by_provider_id(self, provider: str, provider_user_id: str) -> OAuthIdentity | None:
        stmt = select(OAuthIdentityModel).where(
            OAuthIdentityModel.provider == provider,
            OAuthIdentityModel.provider_user_id == provider_user_id,
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return _to_domain(row) if row else None

    def add(self, identity: OAuthIdentity) -> None:
        row = OAuthIdentityModel(
            id=identity.id,
            user_id=identity.user_id,
            provider=identity.provider,
            provider_user_id=identity.provider_user_id,
        )
        self._session.add(row)
        self._session.flush()
