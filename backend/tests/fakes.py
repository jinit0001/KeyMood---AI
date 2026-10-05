"""
In-memory fake repositories. Per LLD.md §5: "unit tests for services use
in-memory fake repositories; no DB required for business-logic tests."
These implement the exact same Protocols as the SQL repositories.
"""
from datetime import datetime
from uuid import UUID

from app.domain.auth.entities import EmailVerification, OAuthIdentity, PasswordReset, RefreshToken, User


class FakeUserRepository:
    def __init__(self):
        self._by_id: dict[UUID, User] = {}

    def get_by_id(self, user_id: UUID) -> User | None:
        return self._by_id.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        for user in self._by_id.values():
            if user.email == email.lower():
                return user
        return None

    def add(self, user: User) -> None:
        self._by_id[user.id] = user

    def update(self, user: User) -> None:
        self._by_id[user.id] = user


class FakeOAuthIdentityRepository:
    def __init__(self):
        self._items: list[OAuthIdentity] = []

    def get_by_provider_id(self, provider: str, provider_user_id: str) -> OAuthIdentity | None:
        for item in self._items:
            if item.provider == provider and item.provider_user_id == provider_user_id:
                return item
        return None

    def add(self, identity: OAuthIdentity) -> None:
        self._items.append(identity)


class FakeEmailVerificationRepository:
    def __init__(self):
        self._by_hash: dict[str, EmailVerification] = {}
        self._by_id: dict[UUID, EmailVerification] = {}

    def add(self, record: EmailVerification) -> None:
        self._by_hash[record.token_hash] = record
        self._by_id[record.id] = record

    def get_by_token_hash(self, token_hash: str) -> EmailVerification | None:
        return self._by_hash.get(token_hash)

    def mark_consumed(self, record_id: UUID, consumed_at: datetime) -> None:
        record = self._by_id[record_id]
        record.consumed_at = consumed_at


class FakePasswordResetRepository:
    def __init__(self):
        self._by_hash: dict[str, PasswordReset] = {}
        self._by_id: dict[UUID, PasswordReset] = {}

    def add(self, record: PasswordReset) -> None:
        self._by_hash[record.token_hash] = record
        self._by_id[record.id] = record

    def get_by_token_hash(self, token_hash: str) -> PasswordReset | None:
        return self._by_hash.get(token_hash)

    def mark_consumed(self, record_id: UUID, consumed_at: datetime) -> None:
        record = self._by_id[record_id]
        record.consumed_at = consumed_at


class FakeRefreshTokenRepository:
    def __init__(self):
        self._by_jti: dict[UUID, RefreshToken] = {}
        self._by_id: dict[UUID, RefreshToken] = {}

    def add(self, token: RefreshToken) -> None:
        self._by_jti[token.jti] = token
        self._by_id[token.id] = token

    def get_by_jti(self, jti: UUID) -> RefreshToken | None:
        return self._by_jti.get(jti)

    def revoke(self, token_id: UUID, revoked_at: datetime) -> None:
        self._by_id[token_id].revoked_at = revoked_at

    def revoke_all_for_user(self, user_id: UUID, revoked_at: datetime) -> None:
        for token in self._by_id.values():
            if token.user_id == user_id and token.revoked_at is None:
                token.revoked_at = revoked_at


class FakeProfileInitializer:
    def __init__(self):
        self.created: dict[UUID, str] = {}

    def create_initial_profile(self, user_id: UUID, display_name: str) -> None:
        self.created[user_id] = display_name


class FakeEmailSender:
    def __init__(self):
        self.sent: list[dict] = []

    def send(self, to: str, subject: str, body_text: str, body_html: str | None = None) -> None:
        self.sent.append({"to": to, "subject": subject, "text": body_text, "html": body_html})

    def last_sent_to(self, email: str) -> dict | None:
        for msg in reversed(self.sent):
            if msg["to"] == email:
                return msg
        return None


class FakeGoogleOAuthProvider:
    """Test double implementing app.domain.auth.ports.OAuthProvider —
    returns a preconfigured OAuthUserInfo instead of calling Google's
    servers, per the instruction not to call real external services in
    unit/API tests."""

    def __init__(self, user_info=None, raise_error: Exception | None = None):
        self._user_info = user_info
        self._raise_error = raise_error

    def verify_id_token(self, raw_id_token: str):
        if self._raise_error:
            raise self._raise_error
        return self._user_info


class FakeAsyncRedis:
    """In-memory stand-in for redis.asyncio.Redis, implementing only the
    three methods app.core.rate_limit.enforce_rate_limit calls (incr,
    expire, ttl). Used to keep API-level tests from requiring a real
    Redis instance, per the instruction not to hit real external
    services in tests."""

    def __init__(self):
        self._counts: dict[str, int] = {}
        self._ttls: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        self._ttls[key] = seconds

    async def ttl(self, key: str) -> int:
        return self._ttls.get(key, 60)
