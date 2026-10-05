from datetime import datetime, timezone

import pytest

from app.core.exceptions import (
    AccountSuspendedError,
    EmailAlreadyExistsError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    RefreshTokenInvalidOrRevokedError,
    TokenInvalidOrExpiredError,
    ValidationError,
)
from app.core.security import jwt as jwt_utils
from app.core.security.password import verify_password
from app.domain.auth.entities import UserStatus
from tests.conftest import VALID_PASSWORD


def _register(service, email="user@example.com", password=VALID_PASSWORD, name="Test User"):
    return service.register(email, password, name)


class TestRegister:
    def test_register_creates_user_and_sends_verification(self, auth_service, fake_email_sender, fake_repos):
        user = _register(auth_service)
        assert user.email == "user@example.com"
        assert user.email_verified is False
        assert user.role.value == "user"
        assert fake_repos["user_repo"].get_by_email("user@example.com") is not None
        assert fake_email_sender.last_sent_to("user@example.com") is not None

    def test_register_creates_initial_profile(self, auth_service, fake_repos):
        user = _register(auth_service, name="Priya S")
        assert fake_repos["profile_initializer"].created[user.id] == "Priya S"

    def test_register_duplicate_email_rejected(self, auth_service):
        _register(auth_service)
        with pytest.raises(EmailAlreadyExistsError):
            _register(auth_service)

    def test_register_weak_password_rejected(self, auth_service):
        with pytest.raises(ValidationError):
            auth_service.register("weak@example.com", "weak", "Name")

    def test_register_stores_hash_not_plaintext(self, auth_service, fake_repos):
        user = _register(auth_service)
        stored = fake_repos["user_repo"].get_by_id(user.id)
        assert stored.password_hash != VALID_PASSWORD
        assert verify_password(VALID_PASSWORD, stored.password_hash)


class TestEmailVerification:
    def test_verify_email_marks_user_verified(self, auth_service, fake_repos, fake_email_sender):
        user = _register(auth_service)
        raw_token = fake_email_sender.sent[0]["text"].split("token=")[1].split("\n")[0]
        auth_service.verify_email(raw_token)
        assert fake_repos["user_repo"].get_by_id(user.id).email_verified is True

    def test_verify_email_invalid_token_rejected(self, auth_service):
        with pytest.raises(Exception):
            auth_service.verify_email("not-a-real-token")

    def test_verify_email_token_cannot_be_reused(self, auth_service, fake_email_sender):
        _register(auth_service)
        raw_token = fake_email_sender.sent[0]["text"].split("token=")[1].split("\n")[0]
        auth_service.verify_email(raw_token)
        with pytest.raises(TokenInvalidOrExpiredError):
            auth_service.verify_email(raw_token)


class TestLogin:
    def _register_and_verify(self, auth_service, fake_email_sender, email="user@example.com"):
        user = _register(auth_service, email=email)
        raw_token = fake_email_sender.last_sent_to(email)["text"].split("token=")[1].split("\n")[0]
        auth_service.verify_email(raw_token)
        return user

    def test_login_succeeds_after_verification(self, auth_service, fake_email_sender):
        self._register_and_verify(auth_service, fake_email_sender)
        pair = auth_service.login("user@example.com", VALID_PASSWORD)
        assert pair.access_token
        assert pair.refresh_token
        assert pair.expires_in == 15 * 60

    def test_login_blocked_before_verification(self, auth_service):
        _register(auth_service)
        with pytest.raises(EmailNotVerifiedError):
            auth_service.login("user@example.com", VALID_PASSWORD)

    def test_login_wrong_password_rejected(self, auth_service, fake_email_sender):
        self._register_and_verify(auth_service, fake_email_sender)
        with pytest.raises(InvalidCredentialsError):
            auth_service.login("user@example.com", "WrongPassword1!")

    def test_login_unknown_email_rejected(self, auth_service):
        with pytest.raises(InvalidCredentialsError):
            auth_service.login("nobody@example.com", VALID_PASSWORD)

    def test_login_suspended_account_rejected(self, auth_service, fake_email_sender, fake_repos):
        user = self._register_and_verify(auth_service, fake_email_sender)
        user.status = UserStatus.SUSPENDED
        fake_repos["user_repo"].update(user)
        with pytest.raises(AccountSuspendedError):
            auth_service.login("user@example.com", VALID_PASSWORD)

    def test_access_token_embeds_role(self, auth_service, fake_email_sender):
        self._register_and_verify(auth_service, fake_email_sender)
        pair = auth_service.login("user@example.com", VALID_PASSWORD)
        payload = jwt_utils.decode_token(pair.access_token, jwt_utils.TokenType.ACCESS)
        assert payload["role"] == "user"


class TestRefreshRotation:
    def _login(self, auth_service, fake_email_sender):
        _register(auth_service, fake_email_sender and None or "user@example.com")

    def _setup_logged_in(self, auth_service, fake_email_sender):
        user = _register(auth_service)
        raw_token = fake_email_sender.sent[0]["text"].split("token=")[1].split("\n")[0]
        auth_service.verify_email(raw_token)
        return auth_service.login("user@example.com", VALID_PASSWORD)

    def test_refresh_issues_new_pair(self, auth_service, fake_email_sender):
        pair = self._setup_logged_in(auth_service, fake_email_sender)
        new_pair = auth_service.refresh(pair.refresh_token)
        assert new_pair.access_token != pair.access_token
        assert new_pair.refresh_token != pair.refresh_token

    def test_old_refresh_token_rejected_after_rotation(self, auth_service, fake_email_sender):
        pair = self._setup_logged_in(auth_service, fake_email_sender)
        auth_service.refresh(pair.refresh_token)
        with pytest.raises(RefreshTokenInvalidOrRevokedError):
            auth_service.refresh(pair.refresh_token)

    def test_new_refresh_token_works(self, auth_service, fake_email_sender):
        pair = self._setup_logged_in(auth_service, fake_email_sender)
        new_pair = auth_service.refresh(pair.refresh_token)
        # Should not raise.
        auth_service.refresh(new_pair.refresh_token)

    def test_revoked_refresh_token_rejected(self, auth_service, fake_email_sender, fake_repos):
        pair = self._setup_logged_in(auth_service, fake_email_sender)
        payload = jwt_utils.decode_token(pair.refresh_token, jwt_utils.TokenType.REFRESH)
        from uuid import UUID
        record = fake_repos["refresh_token_repo"].get_by_jti(UUID(payload["jti"]))
        fake_repos["refresh_token_repo"].revoke(record.id, datetime.now(timezone.utc))
        with pytest.raises(RefreshTokenInvalidOrRevokedError):
            auth_service.refresh(pair.refresh_token)


class TestLogout:
    def _setup_logged_in(self, auth_service, fake_email_sender):
        _register(auth_service)
        raw_token = fake_email_sender.sent[0]["text"].split("token=")[1].split("\n")[0]
        auth_service.verify_email(raw_token)
        return auth_service.login("user@example.com", VALID_PASSWORD)

    def test_logout_revokes_refresh_token(self, auth_service, fake_email_sender):
        pair = self._setup_logged_in(auth_service, fake_email_sender)
        auth_service.logout(pair.refresh_token)
        with pytest.raises(RefreshTokenInvalidOrRevokedError):
            auth_service.refresh(pair.refresh_token)


class TestPasswordReset:
    def _setup_logged_in(self, auth_service, fake_email_sender):
        _register(auth_service)
        raw_token = fake_email_sender.sent[0]["text"].split("token=")[1].split("\n")[0]
        auth_service.verify_email(raw_token)
        return auth_service.login("user@example.com", VALID_PASSWORD)

    def test_forgot_password_unknown_email_does_not_raise(self, auth_service):
        auth_service.request_password_reset("nobody@example.com")  # must not raise

    def test_forgot_password_sends_email_for_known_user(self, auth_service, fake_email_sender):
        _register(auth_service)
        fake_email_sender.sent.clear()
        auth_service.request_password_reset("user@example.com")
        assert fake_email_sender.last_sent_to("user@example.com") is not None

    def test_reset_password_changes_password_and_allows_login(self, auth_service, fake_email_sender):
        _register(auth_service)
        raw_verify_token = fake_email_sender.sent[0]["text"].split("token=")[1].split("\n")[0]
        auth_service.verify_email(raw_verify_token)

        fake_email_sender.sent.clear()
        auth_service.request_password_reset("user@example.com")
        raw_reset_token = fake_email_sender.sent[0]["text"].split("token=")[1].split("\n")[0]

        new_password = "N3wStr0ng!Pass"
        auth_service.reset_password(raw_reset_token, new_password)

        pair = auth_service.login("user@example.com", new_password)
        assert pair.access_token

        with pytest.raises(InvalidCredentialsError):
            auth_service.login("user@example.com", VALID_PASSWORD)

    def test_reset_password_revokes_all_sessions(self, auth_service, fake_email_sender, fake_repos):
        pair = self._setup_logged_in(auth_service, fake_email_sender)

        fake_email_sender.sent.clear()
        auth_service.request_password_reset("user@example.com")
        raw_reset_token = fake_email_sender.sent[0]["text"].split("token=")[1].split("\n")[0]
        auth_service.reset_password(raw_reset_token, "N3wStr0ng!Pass")

        with pytest.raises(RefreshTokenInvalidOrRevokedError):
            auth_service.refresh(pair.refresh_token)

    def test_reset_password_token_cannot_be_reused(self, auth_service, fake_email_sender):
        _register(auth_service)
        fake_email_sender.sent.clear()
        auth_service.request_password_reset("user@example.com")
        raw_reset_token = fake_email_sender.sent[0]["text"].split("token=")[1].split("\n")[0]
        auth_service.reset_password(raw_reset_token, "N3wStr0ng!Pass")
        with pytest.raises(TokenInvalidOrExpiredError):
            auth_service.reset_password(raw_reset_token, "AnotherStr0ng!Pass")


class TestGoogleLogin:
    def test_new_google_user_is_created_and_verified(self, fake_repos, fake_email_sender):
        from app.domain.auth.entities import OAuthUserInfo
        from app.services.auth_service import AuthService
        from tests.fakes import FakeGoogleOAuthProvider

        google_provider = FakeGoogleOAuthProvider(
            user_info=OAuthUserInfo(
                provider_user_id="google-sub-123",
                email="googleuser@example.com",
                email_verified=True,
                display_name="Google User",
            )
        )
        service = AuthService(
            user_repo=fake_repos["user_repo"],
            oauth_repo=fake_repos["oauth_repo"],
            email_verification_repo=fake_repos["email_verification_repo"],
            password_reset_repo=fake_repos["password_reset_repo"],
            refresh_token_repo=fake_repos["refresh_token_repo"],
            profile_initializer=fake_repos["profile_initializer"],
            email_sender=fake_email_sender,
            google_provider=google_provider,
            access_token_expire_minutes=15,
            email_verification_expire_hours=24,
            password_reset_expire_minutes=30,
            frontend_base_url="http://localhost:5173",
        )

        pair = service.login_with_google("fake-id-token")
        assert pair.access_token
        user = fake_repos["user_repo"].get_by_email("googleuser@example.com")
        assert user is not None
        assert user.email_verified is True
        assert user.password_hash is None
