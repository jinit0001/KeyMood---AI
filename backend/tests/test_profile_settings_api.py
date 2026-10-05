"""
API-level tests for Profile & Settings, run against REAL Postgres — not
fakes. This is deliberate: Module 2 introduces new SQL repositories
(profile_repository.py, settings_repository.py, data_export_repository.py)
that fakes-based unit tests (test_profile_service.py, test_settings_service.py)
never touch. JSONB round-tripping (dataclass -> dict -> JSONB -> dict ->
dataclass) and real foreign-key behavior are exactly the kind of thing
that only breaks against a real database — see get_db's commit fix,
found via this same style of real-DB testing on Module 1.

Only email_sender and google_provider are faked (genuinely external
services this test environment can't reach); everything else — user
repo, profile repo, settings repo, export repo, refresh token repo — is
the real SQL implementation against a real (test) Postgres database.
"""
import re
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_auth_service
from app.infrastructure.db.repositories.email_verification_repository import SqlEmailVerificationRepository
from app.infrastructure.db.repositories.oauth_identity_repository import SqlOAuthIdentityRepository
from app.infrastructure.db.repositories.password_reset_repository import SqlPasswordResetRepository
from app.infrastructure.db.repositories.profile_initializer import SqlProfileInitializer
from app.infrastructure.db.repositories.refresh_token_repository import SqlRefreshTokenRepository
from app.infrastructure.db.repositories.user_repository import SqlUserRepository
from app.infrastructure.db.session import get_db
from app.main import app
from app.services.auth_service import AuthService
from tests.fakes import FakeAsyncRedis, FakeEmailSender, FakeGoogleOAuthProvider

VALID_PASSWORD = "Str0ng!Passw0rd"


def _real_auth_service_factory(email_sender: FakeEmailSender):
    def _override(db: Session = Depends(get_db)):
        return AuthService(
            user_repo=SqlUserRepository(db),
            oauth_repo=SqlOAuthIdentityRepository(db),
            email_verification_repo=SqlEmailVerificationRepository(db),
            password_reset_repo=SqlPasswordResetRepository(db),
            refresh_token_repo=SqlRefreshTokenRepository(db),
            profile_initializer=SqlProfileInitializer(db),
            email_sender=email_sender,
            google_provider=FakeGoogleOAuthProvider(),
            access_token_expire_minutes=15,
            email_verification_expire_hours=24,
            password_reset_expire_minutes=30,
            frontend_base_url="http://localhost",
        )

    return _override


def _extract_token(email_sender: FakeEmailSender, email: str) -> str:
    for sent in email_sender.sent:
        if sent["to"] == email:
            match = re.search(r"token=([\w\-.]+)", sent["text"])
            if match:
                return match.group(1)
    raise AssertionError(f"No email captured for {email}")


@pytest.fixture
def email_sender():
    return FakeEmailSender()


@pytest.fixture
def client(email_sender):
    # Real Postgres for everything (see module docstring) — but Redis
    # stays faked here, same as test_auth_api.py: a real async Redis
    # client's connection gets bound to the event loop of the
    # TestClient context that created it, and a fresh event loop per
    # test (each `with TestClient(app)`) makes that stale connection
    # unusable ("Event loop is closed"). Rate limiting itself is
    # Module 1's concern and already covered there; faking it here
    # keeps this suite focused on what it's actually verifying —
    # real DB persistence for Profile & Settings.
    import app.core.rate_limit as rate_limit_module

    previous_redis_client = rate_limit_module._redis_client
    rate_limit_module._redis_client = FakeAsyncRedis()

    app.dependency_overrides[get_auth_service] = _real_auth_service_factory(email_sender)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    rate_limit_module._redis_client = previous_redis_client


def _register_verify_login(client, email_sender, email=None):
    email = email or f"profile-{uuid4().hex[:10]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": VALID_PASSWORD, "display_name": "Original Name"},
    )
    token = _extract_token(email_sender, email)
    client.post("/api/v1/auth/verify-email", json={"token": token})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})
    pair = resp.json()
    return {"Authorization": f"Bearer {pair['access_token']}"}, email


class TestProfileEndpoints:
    def test_get_profile_returns_auto_created_row(self, client, email_sender):
        headers, _ = _register_verify_login(client, email_sender)
        resp = client.get("/api/v1/profile/me", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["display_name"] == "Original Name"
        assert body["timezone"] == "UTC"

    def test_get_profile_requires_auth(self, client, email_sender):
        resp = client.get("/api/v1/profile/me")
        assert resp.status_code == 401

    def test_patch_updates_and_persists_across_requests(self, client, email_sender):
        headers, _ = _register_verify_login(client, email_sender)
        patch_resp = client.patch(
            "/api/v1/profile/me",
            json={"display_name": "Updated Name", "bio": "Building KeyMood AI"},
            headers=headers,
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["display_name"] == "Updated Name"

        # Real second request, real fresh DB read — not the same in-memory
        # object. This is what actually proves the write persisted.
        get_resp = client.get("/api/v1/profile/me", headers=headers)
        assert get_resp.json()["display_name"] == "Updated Name"
        assert get_resp.json()["bio"] == "Building KeyMood AI"

    def test_patch_partial_update_leaves_other_fields(self, client, email_sender):
        headers, _ = _register_verify_login(client, email_sender)
        client.patch("/api/v1/profile/me", json={"bio": "first bio"}, headers=headers)
        resp = client.patch("/api/v1/profile/me", json={"display_name": "Only Name"}, headers=headers)
        assert resp.json()["display_name"] == "Only Name"
        assert resp.json()["bio"] == "first bio"

    def test_patch_empty_display_name_rejected(self, client, email_sender):
        headers, _ = _register_verify_login(client, email_sender)
        resp = client.patch("/api/v1/profile/me", json={"display_name": ""}, headers=headers)
        assert resp.status_code == 422  # pydantic min_length=1 catches this at the schema level

    def test_patch_bio_too_long_rejected(self, client, email_sender):
        headers, _ = _register_verify_login(client, email_sender)
        resp = client.patch("/api/v1/profile/me", json={"bio": "x" * 301}, headers=headers)
        assert resp.status_code == 422


class TestPrivacySettingsEndpoints:
    def test_get_returns_defaults_on_first_access(self, client, email_sender):
        headers, _ = _register_verify_login(client, email_sender)
        resp = client.get("/api/v1/settings/privacy", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["keystroke_analysis"] is True

    def test_patch_persists_jsonb_roundtrip_correctly(self, client, email_sender):
        """The real risk area: dataclass -> dict -> JSONB -> dict ->
        dataclass. A bug here wouldn't show up in fakes-based tests at all."""
        headers, _ = _register_verify_login(client, email_sender)
        client.patch("/api/v1/settings/privacy", json={"guardian_sharing": False}, headers=headers)

        # Fresh GET, real DB read.
        resp = client.get("/api/v1/settings/privacy", headers=headers)
        body = resp.json()
        assert body["guardian_sharing"] is False
        assert body["keystroke_analysis"] is True  # untouched field survives the round-trip


class TestNotificationSettingsEndpoints:
    def test_get_defaults(self, client, email_sender):
        headers, _ = _register_verify_login(client, email_sender)
        resp = client.get("/api/v1/settings/notifications", headers=headers)
        assert resp.json()["sos_alerts"] is True

    def test_patch_and_persist(self, client, email_sender):
        headers, _ = _register_verify_login(client, email_sender)
        client.patch("/api/v1/settings/notifications", json={"messages": False}, headers=headers)
        resp = client.get("/api/v1/settings/notifications", headers=headers)
        assert resp.json()["messages"] is False


class TestAIPreferencesEndpoints:
    def test_get_defaults(self, client, email_sender):
        headers, _ = _register_verify_login(client, email_sender)
        resp = client.get("/api/v1/settings/ai-preferences", headers=headers)
        assert resp.json()["companion_tone"] == "supportive"

    def test_patch_valid_values_persist(self, client, email_sender):
        headers, _ = _register_verify_login(client, email_sender)
        client.patch(
            "/api/v1/settings/ai-preferences",
            json={"companion_tone": "direct", "coaching_frequency": "high"},
            headers=headers,
        )
        resp = client.get("/api/v1/settings/ai-preferences", headers=headers)
        assert resp.json()["companion_tone"] == "direct"
        assert resp.json()["coaching_frequency"] == "high"

    def test_patch_invalid_tone_rejected_with_400(self, client, email_sender):
        headers, _ = _register_verify_login(client, email_sender)
        resp = client.patch(
            "/api/v1/settings/ai-preferences", json={"companion_tone": "sarcastic"}, headers=headers
        )
        assert resp.status_code == 400


class TestExportEndpoint:
    def test_request_export_returns_202_with_pending_status(self, client, email_sender):
        headers, _ = _register_verify_login(client, email_sender)
        resp = client.post("/api/v1/settings/export", headers=headers)
        assert resp.status_code == 202
        assert resp.json()["status"] == "pending"


class TestDeleteAccountEndpoint:
    def test_correct_password_deletes_and_subsequent_login_fails(self, client, email_sender):
        headers, email = _register_verify_login(client, email_sender)
        resp = client.request(
            "DELETE", "/api/v1/settings/account", json={"password": VALID_PASSWORD}, headers=headers
        )
        assert resp.status_code == 204

        # Real re-verification: a deleted account should not be able to log in again.
        login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})
        assert login_resp.status_code in (401, 403)

    def test_wrong_password_returns_401_and_account_survives(self, client, email_sender):
        headers, email = _register_verify_login(client, email_sender)
        resp = client.request(
            "DELETE", "/api/v1/settings/account", json={"password": "totally-wrong"}, headers=headers
        )
        assert resp.status_code == 401

        # Account should still be usable — this proves the wrong-password
        # path didn't delete anything despite returning an error.
        login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})
        assert login_resp.status_code == 200
