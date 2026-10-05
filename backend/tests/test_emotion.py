import re
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_auth_service
from app.domain.emotion import EmotionBaseline, KeystrokeFeatureBatch
from app.infrastructure.db.repositories.email_verification_repository import SqlEmailVerificationRepository
from app.infrastructure.db.repositories.oauth_identity_repository import SqlOAuthIdentityRepository
from app.infrastructure.db.repositories.password_reset_repository import SqlPasswordResetRepository
from app.infrastructure.db.repositories.profile_initializer import SqlProfileInitializer
from app.infrastructure.db.repositories.refresh_token_repository import SqlRefreshTokenRepository
from app.infrastructure.db.repositories.user_repository import SqlUserRepository
from app.infrastructure.db.session import get_db
from app.main import app
from app.services.auth_service import AuthService
from app.services.emotion import classify, update_baseline
from tests.fakes import FakeAsyncRedis, FakeEmailSender, FakeGoogleOAuthProvider

VALID_PASSWORD = "Str0ng!Passw0rd"


def _batch(**kw) -> KeystrokeFeatureBatch:
    now = datetime.now(timezone.utc)
    defaults = dict(id=uuid4(), session_id=uuid4(), avg_hold_time=100.0, typing_speed=45.0,
                     avg_interkey_delay=180.0, error_rate=0.05, total_keys=200, window_start=now, window_end=now)
    defaults.update(kw)
    return KeystrokeFeatureBatch(**defaults)


def _baseline(sample_count=10, **kw) -> EmotionBaseline:
    defaults = dict(user_id=uuid4(), avg_hold_time=100.0, typing_speed=45.0, avg_interkey_delay=180.0,
                     error_rate=0.05, sample_count=sample_count, updated_at=datetime.now(timezone.utc))
    defaults.update(kw)
    return EmotionBaseline(**defaults)


class TestClassifier:
    def test_high_error_rate_is_stressed(self):
        label, _ = classify(_batch(error_rate=0.25), _baseline())
        assert label == "stressed"

    def test_much_slower_typing_is_tired(self):
        label, _ = classify(_batch(typing_speed=30.0, error_rate=0.04), _baseline(typing_speed=50.0))
        assert label == "tired"

    def test_much_faster_low_error_is_happy(self):
        label, _ = classify(_batch(typing_speed=65.0, error_rate=0.01), _baseline())
        assert label == "happy"

    def test_matching_baseline_is_calm(self):
        label, _ = classify(_batch(), _baseline())
        assert label == "calm"

    def test_confidence_in_valid_range(self):
        for baseline in (None, _baseline()):
            _, conf = classify(_batch(), baseline)
            assert 50.0 <= conf <= 97.0

    def test_no_baseline_still_works(self):
        label, _ = classify(_batch(), None)
        assert label in {"calm", "focused", "stressed", "tired", "happy"}

    def test_baseline_update_running_average(self):
        updated = update_baseline(_batch(typing_speed=60.0), _baseline(typing_speed=40.0, sample_count=1))
        assert 40.0 < updated["typing_speed"] < 60.0
        assert updated["sample_count"] == 2

    def test_first_batch_becomes_baseline(self):
        updated = update_baseline(_batch(typing_speed=60.0), None)
        assert updated["typing_speed"] == 60.0
        assert updated["sample_count"] == 1


# --- Real Postgres + WebSocket tests ---

def _auth_override(email_sender):
    def _override(db: Session = Depends(get_db)):
        return AuthService(
            user_repo=SqlUserRepository(db), oauth_repo=SqlOAuthIdentityRepository(db),
            email_verification_repo=SqlEmailVerificationRepository(db),
            password_reset_repo=SqlPasswordResetRepository(db), refresh_token_repo=SqlRefreshTokenRepository(db),
            profile_initializer=SqlProfileInitializer(db), email_sender=email_sender,
            google_provider=FakeGoogleOAuthProvider(), access_token_expire_minutes=15,
            email_verification_expire_hours=24, password_reset_expire_minutes=30,
            frontend_base_url="http://localhost",
        )
    return _override


def _extract_token(email_sender, email):
    for sent in email_sender.sent:
        if sent["to"] == email:
            m = re.search(r"token=([\w\-.]+)", sent["text"])
            if m:
                return m.group(1)
    raise AssertionError("no email captured")


@pytest.fixture
def email_sender():
    return FakeEmailSender()


@pytest.fixture
def client(email_sender):
    import app.core.rate_limit as rl
    prev = rl._redis_client
    rl._redis_client = FakeAsyncRedis()
    app.dependency_overrides[get_auth_service] = _auth_override(email_sender)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    rl._redis_client = prev


def _login(client, email_sender):
    email = f"emotion-{uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": VALID_PASSWORD, "display_name": "T"})
    token = _extract_token(email_sender, email)
    client.post("/api/v1/auth/verify-email", json={"token": token})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})
    return resp.json()["access_token"], {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _payload(**kw):
    p = {"avg_hold_time": 100.0, "typing_speed": 45.0, "avg_interkey_delay": 180.0, "error_rate": 0.05,
         "total_keys": 150, "window_start": "2026-01-01T10:00:00Z", "window_end": "2026-01-01T10:00:20Z"}
    p.update(kw)
    return p


class TestEmotionApiReal:
    def test_rest_endpoints_empty_before_any_data(self, client, email_sender):
        _, headers = _login(client, email_sender)
        assert client.get("/api/v1/emotion/current", headers=headers).json() is None
        assert client.get("/api/v1/emotion/history", headers=headers).json() == []
        assert client.get("/api/v1/emotion/baseline", headers=headers).json() is None

    def test_requires_auth(self, client, email_sender):
        assert client.get("/api/v1/emotion/current").status_code == 401

    def test_ws_rejects_no_token(self, client, email_sender):
        with pytest.raises(Exception):
            with client.websocket_connect("/api/v1/emotion/stream"):
                pass

    def test_ws_stream_persists_across_separate_rest_request(self, client, email_sender):
        token, headers = _login(client, email_sender)
        with client.websocket_connect(f"/api/v1/emotion/stream?token={token}") as ws:
            ws.send_json(_payload(typing_speed=70.0, error_rate=0.01))
            data = ws.receive_json()
            assert data["label"] in {"calm", "focused", "stressed", "tired", "happy"}

        resp = client.get("/api/v1/emotion/current", headers=headers)
        assert resp.json() is not None

    def test_ws_updates_baseline(self, client, email_sender):
        token, headers = _login(client, email_sender)
        with client.websocket_connect(f"/api/v1/emotion/stream?token={token}") as ws:
            ws.send_json(_payload())
            ws.receive_json()
            ws.send_json(_payload())
            ws.receive_json()
        assert client.get("/api/v1/emotion/baseline", headers=headers).json()["sample_count"] == 2

    def test_ws_consent_denied_via_settings_module_closes_connection(self, client, email_sender):
        """Cross-module: Module 2's privacy.keystroke_analysis toggle genuinely gates the WS."""
        token, headers = _login(client, email_sender)
        client.patch("/api/v1/settings/privacy", json={"keystroke_analysis": False}, headers=headers)
        with pytest.raises(Exception):
            with client.websocket_connect(f"/api/v1/emotion/stream?token={token}") as ws:
                ws.send_json(_payload())
                ws.receive_json()

    def test_ws_malformed_batch_does_not_kill_connection(self, client, email_sender):
        token, _ = _login(client, email_sender)
        with client.websocket_connect(f"/api/v1/emotion/stream?token={token}") as ws:
            ws.send_json({"typing_speed": "not-a-number"})
            assert "error" in ws.receive_json()
            ws.send_json(_payload())
            assert "label" in ws.receive_json()

    def test_recalibrate_resets_sample_count(self, client, email_sender):
        token, headers = _login(client, email_sender)
        with client.websocket_connect(f"/api/v1/emotion/stream?token={token}") as ws:
            ws.send_json(_payload())
            ws.receive_json()
        assert client.get("/api/v1/emotion/baseline", headers=headers).json()["sample_count"] == 1

        resp = client.post("/api/v1/emotion/baseline/recalibrate", headers=headers)
        assert resp.json()["sample_count"] == 0
