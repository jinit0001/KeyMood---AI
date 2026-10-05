"""
API-level tests for the Auth router. Uses FastAPI's TestClient against
the real app, with app.dependency_overrides swapping get_auth_service
for an AuthService built from in-memory fakes, and rate-limit/current-user
dependencies overridden so no real Redis/DB/SMTP/Google call ever happens
— satisfying the instruction not to hit real external services in tests.
"""
import pytest
from fastapi import Header
from fastapi.testclient import TestClient

from app.api.v1.auth.dependencies import get_auth_service, get_current_user
from app.core.security import jwt as jwt_utils
from app.main import app
from app.services.auth_service import AuthService
from tests.conftest import VALID_PASSWORD
from tests.fakes import (
    FakeAsyncRedis,
    FakeEmailSender,
    FakeEmailVerificationRepository,
    FakeGoogleOAuthProvider,
    FakeOAuthIdentityRepository,
    FakePasswordResetRepository,
    FakeProfileInitializer,
    FakeRefreshTokenRepository,
    FakeUserRepository,
)
from uuid import UUID


def _no_op_rate_limit():
    async def _dep():
        return None
    return _dep


@pytest.fixture
def repos():
    return {
        "user_repo": FakeUserRepository(),
        "oauth_repo": FakeOAuthIdentityRepository(),
        "email_verification_repo": FakeEmailVerificationRepository(),
        "password_reset_repo": FakePasswordResetRepository(),
        "refresh_token_repo": FakeRefreshTokenRepository(),
        "profile_initializer": FakeProfileInitializer(),
    }


@pytest.fixture
def email_sender():
    return FakeEmailSender()


@pytest.fixture
def google_provider():
    return FakeGoogleOAuthProvider()


@pytest.fixture
def service(repos, email_sender, google_provider):
    return AuthService(
        user_repo=repos["user_repo"],
        oauth_repo=repos["oauth_repo"],
        email_verification_repo=repos["email_verification_repo"],
        password_reset_repo=repos["password_reset_repo"],
        refresh_token_repo=repos["refresh_token_repo"],
        profile_initializer=repos["profile_initializer"],
        email_sender=email_sender,
        google_provider=google_provider,
        access_token_expire_minutes=15,
        email_verification_expire_hours=24,
        password_reset_expire_minutes=30,
        frontend_base_url="http://localhost:5173",
    )


@pytest.fixture
def client(service, repos):
    # Override the real service with our fake-backed one, and replace the
    # rate limiter's Redis client with an in-memory fake — this is what
    # keeps these tests from requiring a real Redis instance, per the
    # instruction not to hit real external services in tests. Fixed
    # window counters still apply, they just count against memory.
    #
    # get_current_user is also overridden here: it's the dependency every
    # protected route uses, and it independently hits the real DB via
    # get_db — without this override, any endpoint requiring auth (like
    # /logout, and every protected route future modules add) would look
    # up the user in real Postgres instead of the fake repo the rest of
    # this fixture uses, and always fail with 401 in a test environment
    # with no matching real DB row.
    import app.core.rate_limit as rate_limit_module

    async def fake_get_current_user(authorization: str = Header(default="")):
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise jwt_utils.InvalidTokenError("Missing or malformed Authorization header.")
        payload = jwt_utils.decode_token(token, jwt_utils.TokenType.ACCESS)
        user = repos["user_repo"].get_by_id(UUID(payload["sub"]))
        if user is None or not user.is_active():
            raise jwt_utils.InvalidTokenError("User no longer active.")
        return user

    app.dependency_overrides[get_auth_service] = lambda: service
    app.dependency_overrides[get_current_user] = fake_get_current_user
    previous_redis_client = rate_limit_module._redis_client
    rate_limit_module._redis_client = FakeAsyncRedis()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    rate_limit_module._redis_client = previous_redis_client


def _extract_token(email_sender: FakeEmailSender, to: str) -> str:
    message = email_sender.last_sent_to(to)
    return message["text"].split("token=")[1].split("\n")[0]


class TestRegisterEndpoint:
    def test_register_success(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": VALID_PASSWORD, "display_name": "New User"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "user_id" in body
        assert body["email_verification_sent"] is True

    def test_register_duplicate_email_returns_409(self, client):
        payload = {"email": "dup@example.com", "password": VALID_PASSWORD, "display_name": "Dup"}
        client.post("/api/v1/auth/register", json=payload)
        resp = client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "EMAIL_ALREADY_EXISTS"
        assert "message" in body["error"]
        assert "details" in body["error"]

    def test_register_weak_password_returns_error(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "weak@example.com", "password": "weak", "display_name": "Weak"},
        )
        assert resp.status_code in (400, 422)
        assert "error" in resp.json()

    def test_register_invalid_email_format_returns_422(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": VALID_PASSWORD, "display_name": "Name"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_register_missing_field_returns_422(self, client):
        resp = client.post("/api/v1/auth/register", json={"email": "a@example.com"})
        assert resp.status_code == 422


class TestLoginEndpoint:
    def _register_and_verify(self, client, email_sender, email="verified@example.com"):
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": VALID_PASSWORD, "display_name": "V User"},
        )
        token = _extract_token(email_sender, email)
        client.post("/api/v1/auth/verify-email", json={"token": token})

    def test_login_success_returns_token_pair(self, client, email_sender):
        self._register_and_verify(client, email_sender)
        resp = client.post(
            "/api/v1/auth/login", json={"email": "verified@example.com", "password": VALID_PASSWORD}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"access_token", "refresh_token", "expires_in"}
        assert body["expires_in"] == 900

    def test_login_wrong_password_returns_401(self, client, email_sender):
        self._register_and_verify(client, email_sender)
        resp = client.post(
            "/api/v1/auth/login", json={"email": "verified@example.com", "password": "WrongPass1!"}
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_login_unverified_email_returns_403(self, client):
        client.post(
            "/api/v1/auth/register",
            json={"email": "unverified@example.com", "password": VALID_PASSWORD, "display_name": "U"},
        )
        resp = client.post(
            "/api/v1/auth/login", json={"email": "unverified@example.com", "password": VALID_PASSWORD}
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"

    def test_login_unknown_user_returns_401_not_404(self, client):
        """API_SPEC.md doesn't document a 404 for login — unknown email
        must not leak account existence via a different status code."""
        resp = client.post(
            "/api/v1/auth/login", json={"email": "nobody@example.com", "password": VALID_PASSWORD}
        )
        assert resp.status_code == 401


class TestVerifyEmailEndpoint:
    def test_verify_email_success(self, client, email_sender):
        client.post(
            "/api/v1/auth/register",
            json={"email": "verify@example.com", "password": VALID_PASSWORD, "display_name": "N"},
        )
        token = _extract_token(email_sender, "verify@example.com")
        resp = client.post("/api/v1/auth/verify-email", json={"token": token})
        assert resp.status_code == 200
        assert resp.json() == {"verified": True}

    def test_verify_email_invalid_token_returns_400(self, client):
        resp = client.post("/api/v1/auth/verify-email", json={"token": "garbage"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "TOKEN_INVALID_OR_EXPIRED"

    def test_verify_email_reused_token_returns_400(self, client, email_sender):
        client.post(
            "/api/v1/auth/register",
            json={"email": "reuse@example.com", "password": VALID_PASSWORD, "display_name": "N"},
        )
        token = _extract_token(email_sender, "reuse@example.com")
        client.post("/api/v1/auth/verify-email", json={"token": token})
        resp = client.post("/api/v1/auth/verify-email", json={"token": token})
        assert resp.status_code == 400


class TestForgotPasswordEndpoint:
    def test_forgot_password_known_email_returns_200(self, client):
        client.post(
            "/api/v1/auth/register",
            json={"email": "known@example.com", "password": VALID_PASSWORD, "display_name": "N"},
        )
        resp = client.post("/api/v1/auth/forgot-password", json={"email": "known@example.com"})
        assert resp.status_code == 200
        assert resp.json() == {"reset_email_sent": True}

    def test_forgot_password_unknown_email_still_returns_200(self, client):
        """Must not reveal account existence per API_SPEC.md."""
        resp = client.post("/api/v1/auth/forgot-password", json={"email": "ghost@example.com"})
        assert resp.status_code == 200
        assert resp.json() == {"reset_email_sent": True}


class TestResetPasswordEndpoint:
    def test_reset_password_success_and_old_password_rejected(self, client, email_sender):
        client.post(
            "/api/v1/auth/register",
            json={"email": "reset@example.com", "password": VALID_PASSWORD, "display_name": "N"},
        )
        verify_token = _extract_token(email_sender, "reset@example.com")
        client.post("/api/v1/auth/verify-email", json={"token": verify_token})

        email_sender.sent.clear()
        client.post("/api/v1/auth/forgot-password", json={"email": "reset@example.com"})
        reset_token = _extract_token(email_sender, "reset@example.com")

        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": reset_token, "new_password": "N3wStr0ng!Pass"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"reset": True}

        old_login = client.post(
            "/api/v1/auth/login", json={"email": "reset@example.com", "password": VALID_PASSWORD}
        )
        assert old_login.status_code == 401

        new_login = client.post(
            "/api/v1/auth/login", json={"email": "reset@example.com", "password": "N3wStr0ng!Pass"}
        )
        assert new_login.status_code == 200

    def test_reset_password_invalid_token_returns_400(self, client):
        resp = client.post(
            "/api/v1/auth/reset-password", json={"token": "garbage", "new_password": "N3wStr0ng!Pass"}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "TOKEN_INVALID_OR_EXPIRED"

    def test_reset_password_weak_new_password_rejected(self, client, email_sender):
        client.post(
            "/api/v1/auth/register",
            json={"email": "weak2@example.com", "password": VALID_PASSWORD, "display_name": "N"},
        )
        email_sender.sent.clear()
        client.post("/api/v1/auth/forgot-password", json={"email": "weak2@example.com"})
        reset_token = _extract_token(email_sender, "weak2@example.com")
        resp = client.post(
            "/api/v1/auth/reset-password", json={"token": reset_token, "new_password": "weak"}
        )
        assert resp.status_code in (400, 422)


class TestGoogleEndpoint:
    def test_google_login_success(self, client, google_provider):
        from app.domain.auth.entities import OAuthUserInfo

        google_provider._user_info = OAuthUserInfo(
            provider_user_id="g-123",
            email="googleapi@example.com",
            email_verified=True,
            display_name="G User",
        )
        resp = client.post("/api/v1/auth/google", json={"id_token": "fake-token"})
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"access_token", "refresh_token", "expires_in"}

    def test_google_login_invalid_token_returns_401(self, client, google_provider):
        from app.core.exceptions import InvalidGoogleTokenError

        google_provider._raise_error = InvalidGoogleTokenError()
        resp = client.post("/api/v1/auth/google", json={"id_token": "bad-token"})
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_GOOGLE_TOKEN"


class TestRefreshEndpoint:
    def _register_verify_login(self, client, email_sender, email="refresh@example.com"):
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": VALID_PASSWORD, "display_name": "N"},
        )
        token = _extract_token(email_sender, email)
        client.post("/api/v1/auth/verify-email", json={"token": token})
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})
        return resp.json()

    def test_refresh_returns_new_pair(self, client, email_sender):
        pair = self._register_verify_login(client, email_sender)
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
        assert resp.status_code == 200
        new_pair = resp.json()
        assert new_pair["access_token"] != pair["access_token"]
        assert new_pair["refresh_token"] != pair["refresh_token"]

    def test_refresh_old_token_rejected_after_rotation(self, client, email_sender):
        pair = self._register_verify_login(client, email_sender)
        client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "REFRESH_TOKEN_INVALID_OR_REVOKED"

    def test_refresh_garbage_token_returns_401(self, client):
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-jwt"})
        assert resp.status_code == 401


class TestLogoutEndpoint:
    def _register_verify_login(self, client, email_sender, email="logout@example.com"):
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": VALID_PASSWORD, "display_name": "N"},
        )
        token = _extract_token(email_sender, email)
        client.post("/api/v1/auth/verify-email", json={"token": token})
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})
        return resp.json()

    def test_logout_requires_authentication(self, client, email_sender):
        pair = self._register_verify_login(client, email_sender)
        resp = client.post("/api/v1/auth/logout", json={"refresh_token": pair["refresh_token"]})
        # No Authorization header supplied — must be rejected, not silently allowed.
        assert resp.status_code == 401

    def test_logout_success_revokes_refresh_token(self, client, email_sender):
        pair = self._register_verify_login(client, email_sender)
        resp = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": pair["refresh_token"]},
            headers={"Authorization": f"Bearer {pair['access_token']}"},
        )
        assert resp.status_code == 204

        refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
        assert refresh_resp.status_code == 401

    def test_logout_malformed_auth_header_returns_401(self, client, email_sender):
        pair = self._register_verify_login(client, email_sender)
        resp = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": pair["refresh_token"]},
            headers={"Authorization": "NotBearer sometoken"},
        )
        assert resp.status_code == 401


class TestErrorEnvelopeShape:
    def test_every_error_response_has_standard_envelope(self, client):
        resp = client.post("/api/v1/auth/verify-email", json={"token": "garbage"})
        body = resp.json()
        assert "error" in body
        assert set(body["error"].keys()) == {"code", "message", "details"}
        assert isinstance(body["error"]["code"], str)
        assert isinstance(body["error"]["message"], str)
        assert isinstance(body["error"]["details"], dict)


class TestHealthEndpoints:
    def test_liveness(self, client):
        resp = client.get("/health/liveness")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
