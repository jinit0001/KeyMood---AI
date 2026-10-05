from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.auth.entities import User, UserRole, UserStatus
from app.infrastructure.db.models.user import UserModel


def _to_domain(row: UserModel) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        email_verified=row.email_verified,
        status=UserStatus(row.status),
        role=UserRole(row.role),
        privacy_consent_at=row.privacy_consent_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class SqlUserRepository:
    """Implements domain.auth.repositories.UserRepository."""

    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, user_id: UUID) -> User | None:
        row = self._session.get(UserModel, user_id)
        return _to_domain(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email.lower())
        row = self._session.execute(stmt).scalar_one_or_none()
        return _to_domain(row) if row else None

    def add(self, user: User) -> None:
        row = UserModel(
            id=user.id,
            email=user.email.lower(),
            password_hash=user.password_hash,
            email_verified=user.email_verified,
            status=user.status.value,
            role=user.role.value,
            privacy_consent_at=user.privacy_consent_at,
        )
        self._session.add(row)
        self._session.flush()

    def update(self, user: User) -> None:
        row = self._session.get(UserModel, user.id)
        if row is None:
            raise ValueError(f"User {user.id} not found for update")
        row.email = user.email.lower()
        row.password_hash = user.password_hash
        row.email_verified = user.email_verified
        row.status = user.status.value
        row.role = user.role.value
        row.privacy_consent_at = user.privacy_consent_at
        row.deleted_at = user.deleted_at
        self._session.flush()
