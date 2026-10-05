"""
Auth domain entities. Framework-agnostic per ARCHITECTURE.md §2 — no
SQLAlchemy, no Pydantic, no FastAPI imports here. Repositories convert
between these and persistence models.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class UserRole(str, Enum):
    """Per approved decision: only the role the existing architecture
    requires (SECURITY.md §2: user, admin) — no additional roles invented."""
    USER = "user"
    ADMIN = "admin"


@dataclass
class User:
    id: UUID
    email: str
    password_hash: str | None  # None for OAuth-only accounts
    email_verified: bool
    status: UserStatus
    role: UserRole
    privacy_consent_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE and self.deleted_at is None


@dataclass
class OAuthIdentity:
    id: UUID
    user_id: UUID
    provider: str
    provider_user_id: str
    created_at: datetime


@dataclass
class EmailVerification:
    id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    consumed_at: datetime | None
    created_at: datetime


@dataclass
class PasswordReset:
    id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    consumed_at: datetime | None
    created_at: datetime


@dataclass
class RefreshToken:
    id: UUID
    user_id: UUID
    token_hash: str
    jti: UUID
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime

    def is_valid(self, now: datetime) -> bool:
        return self.revoked_at is None and self.expires_at > now


@dataclass
class OAuthUserInfo:
    """Provider-agnostic result of verifying an external OAuth identity
    token. Returned by any OAuthProvider implementation (ports.py) —
    infrastructure/oauth/google_provider.py is one such implementation."""
    provider_user_id: str
    email: str
    email_verified: bool
    display_name: str | None
