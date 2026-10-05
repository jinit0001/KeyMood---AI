"""
AuthService — orchestrates every Auth use case. Depends only on domain
Protocols (LLD.md §5/§6), never on SQLAlchemy or FastAPI. This is what
lets tests/test_auth_service.py exercise every flow with in-memory fakes.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.core.exceptions import (
    AccountSuspendedError,
    EmailAlreadyExistsError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    RefreshTokenInvalidOrRevokedError,
    TokenInvalidOrExpiredError,
    UnauthorizedError,
    ValidationError,
)
from app.core.security import jwt as jwt_utils
from app.core.security.password import hash_password, validate_password_policy, verify_password
from app.domain.auth.entities import (
    EmailVerification,
    OAuthIdentity,
    PasswordReset,
    RefreshToken,
    User,
    UserRole,
    UserStatus,
)
from app.domain.auth.ports import EmailSender, OAuthProvider
from app.domain.auth.repositories import (
    EmailVerificationRepository,
    OAuthIdentityRepository,
    PasswordResetRepository,
    ProfileInitializer,
    RefreshTokenRepository,
    UserRepository,
)
from app.services.email_templates import build_password_reset_email, build_verification_email

logger = logging.getLogger("keymood.auth")


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        oauth_repo: OAuthIdentityRepository,
        email_verification_repo: EmailVerificationRepository,
        password_reset_repo: PasswordResetRepository,
        refresh_token_repo: RefreshTokenRepository,
        profile_initializer: ProfileInitializer,
        email_sender: EmailSender,
        google_provider: OAuthProvider,
        access_token_expire_minutes: int,
        email_verification_expire_hours: int,
        password_reset_expire_minutes: int,
        frontend_base_url: str,
        auto_verify_email: bool = False,
    ):
        self._users = user_repo
        self._oauth = oauth_repo
        self._email_verifications = email_verification_repo
        self._password_resets = password_reset_repo
        self._refresh_tokens = refresh_token_repo
        self._profile_initializer = profile_initializer
        self._email_sender = email_sender
        self._google = google_provider
        self._access_token_expire_minutes = access_token_expire_minutes
        self._email_verification_expire_hours = email_verification_expire_hours
        self._password_reset_expire_minutes = password_reset_expire_minutes
        self._frontend_base_url = frontend_base_url
        self._auto_verify_email = auto_verify_email

    # ---------------------------------------------------------------
    # Registration
    # ---------------------------------------------------------------
    def register(self, email: str, password: str, display_name: str) -> User:
        errors = validate_password_policy(password)
        if errors:
            raise ValidationError("Password does not meet policy requirements.", {"errors": errors})

        normalized_email = email.strip().lower()
        if self._users.get_by_email(normalized_email) is not None:
            raise EmailAlreadyExistsError()

        now = datetime.now(timezone.utc)
        user = User(
            id=uuid4(),
            email=normalized_email,
            password_hash=hash_password(password),
            email_verified=self._auto_verify_email,
            status=UserStatus.ACTIVE,
            role=UserRole.USER,
            privacy_consent_at=None,
            created_at=now,
            updated_at=now,
        )
        self._users.add(user)
        self._profile_initializer.create_initial_profile(user.id, display_name.strip())
        if not self._auto_verify_email:
            self._issue_email_verification(user)
        logger.info("user_registered", extra={"user_id": str(user.id)})
        return user

    def _issue_email_verification(self, user: User) -> None:
        raw_token = jwt_utils.create_email_verification_token(str(user.id))
        now = datetime.now(timezone.utc)
        record = EmailVerification(
            id=uuid4(),
            user_id=user.id,
            token_hash=jwt_utils.hash_token(raw_token),
            expires_at=now + timedelta(hours=self._email_verification_expire_hours),
            consumed_at=None,
            created_at=now,
        )
        self._email_verifications.add(record)
        subject, text, html = build_verification_email(self._frontend_base_url, raw_token)
        self._email_sender.send(user.email, subject, text, html)

    # ---------------------------------------------------------------
    # Email verification
    # ---------------------------------------------------------------
    def verify_email(self, raw_token: str) -> None:
        try:
            payload = jwt_utils.decode_token(raw_token, jwt_utils.TokenType.EMAIL_VERIFICATION)
        except UnauthorizedError as exc:
            # decode_token raises UnauthorizedError (401) for malformed/expired
            # JWTs, which is correct for protected-route auth — but this is a
            # business-flow token verification, where API_SPEC.md wants 400
            # TOKEN_INVALID_OR_EXPIRED instead. Re-map it here.
            raise TokenInvalidOrExpiredError() from exc
        token_hash = jwt_utils.hash_token(raw_token)

        record = self._email_verifications.get_by_token_hash(token_hash)
        if record is None or record.consumed_at is not None:
            raise TokenInvalidOrExpiredError()

        now = datetime.now(timezone.utc)
        if record.expires_at <= now:
            raise TokenInvalidOrExpiredError()

        user = self._users.get_by_id(UUID(payload["sub"]))
        if user is None:
            raise TokenInvalidOrExpiredError()

        user.email_verified = True
        user.updated_at = now
        self._users.update(user)
        self._email_verifications.mark_consumed(record.id, now)
        logger.info("email_verified", extra={"user_id": str(user.id)})

    # ---------------------------------------------------------------
    # Login
    # ---------------------------------------------------------------
    def login(self, email: str, password: str) -> TokenPair:
        user = self._users.get_by_email(email.strip().lower())
        if user is None or user.password_hash is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()

        if user.status == UserStatus.DELETED:
            # Deliberately the same error as "wrong password" rather than a
            # distinct one — telling an attacker an account was deleted is
            # its own small information leak (account enumeration), same
            # reasoning as not revealing whether an email is registered.
            raise InvalidCredentialsError()
        if user.status == UserStatus.SUSPENDED:
            raise AccountSuspendedError()
        if not user.email_verified:
            raise EmailNotVerifiedError()

        logger.info("user_logged_in", extra={"user_id": str(user.id)})
        return self._issue_token_pair(user)

    def _issue_token_pair(self, user: User) -> TokenPair:
        access_token = jwt_utils.create_access_token(str(user.id), user.role.value)
        refresh_token, jti, expires_at = jwt_utils.create_refresh_token(str(user.id))

        record = RefreshToken(
            id=uuid4(),
            user_id=user.id,
            token_hash=jwt_utils.hash_token(refresh_token),
            jti=UUID(jti),
            expires_at=expires_at,
            revoked_at=None,
            created_at=datetime.now(timezone.utc),
        )
        self._refresh_tokens.add(record)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self._access_token_expire_minutes * 60,
        )

    # ---------------------------------------------------------------
    # Refresh — rotation on every use
    # ---------------------------------------------------------------
    def refresh(self, raw_refresh_token: str) -> TokenPair:
        payload = jwt_utils.decode_token(raw_refresh_token, jwt_utils.TokenType.REFRESH)
        jti = UUID(payload["jti"])

        record = self._refresh_tokens.get_by_jti(jti)
        now = datetime.now(timezone.utc)
        if record is None or not record.is_valid(now):
            raise RefreshTokenInvalidOrRevokedError()
        if record.token_hash != jwt_utils.hash_token(raw_refresh_token):
            # Signature/jti matched but stored hash didn't — treat as compromised.
            raise RefreshTokenInvalidOrRevokedError()

        user = self._users.get_by_id(record.user_id)
        if user is None or not user.is_active():
            raise RefreshTokenInvalidOrRevokedError()

        # Rotation: invalidate the old token before issuing a new pair, so a
        # replayed old token is rejected even if the new pair fails to reach the client.
        self._refresh_tokens.revoke(record.id, now)
        logger.info("refresh_token_rotated", extra={"user_id": str(user.id)})
        return self._issue_token_pair(user)

    # ---------------------------------------------------------------
    # Logout
    # ---------------------------------------------------------------
    def logout(self, raw_refresh_token: str) -> None:
        payload = jwt_utils.decode_token(raw_refresh_token, jwt_utils.TokenType.REFRESH)
        jti = UUID(payload["jti"])
        record = self._refresh_tokens.get_by_jti(jti)
        if record is None:
            raise RefreshTokenInvalidOrRevokedError()
        self._refresh_tokens.revoke(record.id, datetime.now(timezone.utc))
        logger.info("user_logged_out", extra={"user_id": str(record.user_id)})

    # ---------------------------------------------------------------
    # Password reset
    # ---------------------------------------------------------------
    def request_password_reset(self, email: str) -> None:
        """Always succeeds from the caller's perspective (API_SPEC.md:
        'does not reveal account existence') — silently no-ops if the
        email isn't registered."""
        user = self._users.get_by_email(email.strip().lower())
        if user is None:
            return

        raw_token = jwt_utils.create_password_reset_token(str(user.id))
        now = datetime.now(timezone.utc)
        record = PasswordReset(
            id=uuid4(),
            user_id=user.id,
            token_hash=jwt_utils.hash_token(raw_token),
            expires_at=now + timedelta(minutes=self._password_reset_expire_minutes),
            consumed_at=None,
            created_at=now,
        )
        self._password_resets.add(record)
        subject, text, html = build_password_reset_email(self._frontend_base_url, raw_token)
        self._email_sender.send(user.email, subject, text, html)
        logger.info("password_reset_requested", extra={"user_id": str(user.id)})

    def reset_password(self, raw_token: str, new_password: str) -> None:
        errors = validate_password_policy(new_password)
        if errors:
            raise ValidationError("Password does not meet policy requirements.", {"errors": errors})

        try:
            payload = jwt_utils.decode_token(raw_token, jwt_utils.TokenType.PASSWORD_RESET)
        except UnauthorizedError as exc:
            raise TokenInvalidOrExpiredError() from exc
        token_hash = jwt_utils.hash_token(raw_token)

        record = self._password_resets.get_by_token_hash(token_hash)
        if record is None or record.consumed_at is not None:
            raise TokenInvalidOrExpiredError()

        now = datetime.now(timezone.utc)
        if record.expires_at <= now:
            raise TokenInvalidOrExpiredError()

        user = self._users.get_by_id(UUID(payload["sub"]))
        if user is None:
            raise TokenInvalidOrExpiredError()

        user.password_hash = hash_password(new_password)
        user.updated_at = now
        self._users.update(user)
        self._password_resets.mark_consumed(record.id, now)

        # SECURITY.md §3: password change invalidates ALL sessions.
        self._refresh_tokens.revoke_all_for_user(user.id, now)
        logger.info("password_reset_completed", extra={"user_id": str(user.id)})

    # ---------------------------------------------------------------
    # Google OAuth
    # ---------------------------------------------------------------
    def login_with_google(self, id_token: str) -> TokenPair:
        google_user = self._google.verify_id_token(id_token)

        identity = self._oauth.get_by_provider_id("google", google_user.provider_user_id)
        if identity is not None:
            user = self._users.get_by_id(identity.user_id)
            if user is None or not user.is_active():
                raise InvalidCredentialsError()
            return self._issue_token_pair(user)

        # No existing link — link to an existing account with the same
        # email, or create a new OAuth-only account (password_hash=None).
        now = datetime.now(timezone.utc)
        user = self._users.get_by_email(google_user.email.strip().lower())
        if user is None:
            user = User(
                id=uuid4(),
                email=google_user.email.strip().lower(),
                password_hash=None,
                email_verified=google_user.email_verified,
                status=UserStatus.ACTIVE,
                role=UserRole.USER,
                privacy_consent_at=None,
                created_at=now,
                updated_at=now,
            )
            self._users.add(user)
            display_name = google_user.display_name or google_user.email.split("@")[0]
            self._profile_initializer.create_initial_profile(user.id, display_name)
        elif google_user.email_verified and not user.email_verified:
            user.email_verified = True
            user.updated_at = now
            self._users.update(user)

        self._oauth.add(
            OAuthIdentity(
                id=uuid4(),
                user_id=user.id,
                provider="google",
                provider_user_id=google_user.provider_user_id,
                created_at=now,
            )
        )
        logger.info("user_registered_via_google", extra={"user_id": str(user.id)})
        return self._issue_token_pair(user)
