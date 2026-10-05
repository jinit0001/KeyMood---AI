"""
Repository interfaces (ports) for the Auth bounded context.

Per LLD.md §5: services depend only on these Protocols, never on
SQLAlchemy directly. Concrete implementations live in
infrastructure/db/repositories/. This is what lets AuthService be unit
tested with in-memory fakes (tests/fakes.py) with no database.
"""
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.auth.entities import (
    EmailVerification,
    OAuthIdentity,
    PasswordReset,
    RefreshToken,
    User,
)


class UserRepository(Protocol):
    def get_by_id(self, user_id: UUID) -> User | None: ...
    def get_by_email(self, email: str) -> User | None: ...
    def add(self, user: User) -> None: ...
    def update(self, user: User) -> None: ...


class OAuthIdentityRepository(Protocol):
    def get_by_provider_id(self, provider: str, provider_user_id: str) -> OAuthIdentity | None: ...
    def add(self, identity: OAuthIdentity) -> None: ...


class EmailVerificationRepository(Protocol):
    def add(self, record: EmailVerification) -> None: ...
    def get_by_token_hash(self, token_hash: str) -> EmailVerification | None: ...
    def mark_consumed(self, record_id: UUID, consumed_at: datetime) -> None: ...


class PasswordResetRepository(Protocol):
    def add(self, record: PasswordReset) -> None: ...
    def get_by_token_hash(self, token_hash: str) -> PasswordReset | None: ...
    def mark_consumed(self, record_id: UUID, consumed_at: datetime) -> None: ...


class RefreshTokenRepository(Protocol):
    def add(self, token: RefreshToken) -> None: ...
    def get_by_jti(self, jti: UUID) -> RefreshToken | None: ...
    def revoke(self, token_id: UUID, revoked_at: datetime) -> None: ...
    def revoke_all_for_user(self, user_id: UUID, revoked_at: datetime) -> None: ...


class ProfileInitializer(Protocol):
    """Narrow port used only by Auth's register() to satisfy the
    display_name field in the register API contract. Module 2 (Profile)
    owns the full read/update repository for user_profiles; this is
    deliberately not that — just enough to create the row that
    Auth's own endpoint contract requires."""

    def create_initial_profile(self, user_id: UUID, display_name: str) -> None: ...
