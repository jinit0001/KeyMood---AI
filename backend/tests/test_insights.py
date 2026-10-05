import re
from datetime import date
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
from app.services.analytics import compute_burnout_risk, compute_period_metrics, compute_wellness_score, period_start_for
from app.services.auth_service import AuthService
from tests.fakes import FakeAsyncRedis, FakeEmailSender, FakeGoogleOAuthProvider

VALID_PASSWORD = "Str0ng!Passw0rd"


class TestAnalyticsPureFunctions:
    def test_period_metrics_empty(self):
        assert compute_period_metrics([])["sample_count"] == 0

    def test_period_metrics_distribution(self):
        m = compute_period_metrics(["happy", "happy", "stressed"])
        assert m["mood_distribution"] == {"happy": 2, "stressed": 1}

    def test_wellness_happy_beats_stressed(self):
        assert compute_wellness_score(["happy"] * 3)[0] > compute_wellness_score(["stressed"] * 3)[0]

    def test_wellness_no_data_defaults_neutral(self):
        assert compute_wellness_score([])[0] == 70.0

    def test_burnout_high_when_mostly_negative(self):
        level, factors = compute_burnout_risk(["stressed", "stressed", "tired", "stressed"])
        assert level == "high"
        assert factors["stressed_ratio"] == 0.75

    def test_burnout_low_when_calm(self):
        assert compute_burnout_risk(["calm"] * 10)[0] == "low"

    def test_burnout_moderate_band(self):
        assert compute_burnout_risk(["stressed", "tired"] + ["calm"] * 5)[0] == "moderate"

    def test_burnout_explainability_fields_present(self):
        _, factors = compute_burnout_risk(["stressed", "calm"])
        assert {"stressed_ratio", "tired_ratio", "sample_count"} <= set(factors)

    def test_period_start_weekly_is_monday(self):
        assert period_start_for("weekly", date(2026, 3, 15)).weekday() == 0

    def test_period_start_monthly_is_first(self):
        assert period_start_for("monthly", date(2026, 3, 15)) == date(2026, 3, 1)

    def test_unknown_period_raises(self):
        with pytest.raises(ValueError):
            period_start_for("yearly", date(2026, 1, 1))


# --- Real Postgres, cross-module with Emotion ---

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
    email = f"insights-{uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": VALID_PASSWORD, "display_name": "T"})
    token = _extract_token(email_sender, email)
    client.post("/api/v1/auth/verify-email", json={"token": token})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})
    return resp.json()["access_token"], {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _stream(client, token, **kw):
    payload = {"avg_hold_time": 100.0, "typing_speed": 45.0, "avg_interkey_delay": 180.0, "error_rate": 0.05,
               "total_keys": 150, "window_start": "2026-01-01T10:00:00Z", "window_end": "2026-01-01T10:00:20Z"}
    payload.update(kw)
    with client.websocket_connect(f"/api/v1/emotion/stream?token={token}") as ws:
        ws.send_json(payload)
        ws.receive_json()


class TestRecommendationsReal:
    def test_current_generates_for_real_recent_emotion(self, client, email_sender):
        token, headers = _login(client, email_sender)
        _stream(client, token, error_rate=0.3)  # classified stressed
        recs = client.get("/api/v1/recommendations/current", headers=headers).json()
        assert len(recs) > 0

    def test_repeat_call_returns_same_active_batch(self, client, email_sender):
        _, headers = _login(client, email_sender)
        first = {r["id"] for r in client.get("/api/v1/recommendations/current", headers=headers).json()}
        second = {r["id"] for r in client.get("/api/v1/recommendations/current", headers=headers).json()}
        assert first == second

    def test_feedback_and_validation(self, client, email_sender):
        _, headers = _login(client, email_sender)
        rec_id = client.get("/api/v1/recommendations/current", headers=headers).json()[0]["id"]
        assert client.post(f"/api/v1/recommendations/{rec_id}/feedback", json={"reaction": "accepted"}, headers=headers).status_code == 200
        assert client.post(f"/api/v1/recommendations/{rec_id}/feedback", json={"reaction": "maybe"}, headers=headers).status_code == 400

    def test_cannot_give_feedback_on_others_recommendation(self, client, email_sender):
        _, headers_a = _login(client, email_sender)
        _, headers_b = _login(client, email_sender)
        rec_id = client.get("/api/v1/recommendations/current", headers=headers_a).json()[0]["id"]
        resp = client.post(f"/api/v1/recommendations/{rec_id}/feedback", json={"reaction": "accepted"}, headers=headers_b)
        assert resp.status_code == 404

    def test_requires_auth(self, client, email_sender):
        assert client.get("/api/v1/recommendations/current").status_code == 401


class TestAnalyticsReal:
    def test_daily_snapshot_reflects_real_streamed_emotion_data(self, client, email_sender):
        """Data written via Emotion's WebSocket in a separate connection,
        read back by Analytics through the shared database."""
        token, headers = _login(client, email_sender)
        _stream(client, token)
        _stream(client, token)
        resp = client.get("/api/v1/analytics/daily", headers=headers)
        assert resp.json()["metrics"]["sample_count"] == 2

    def test_snapshot_is_cached_not_recomputed(self, client, email_sender):
        token, headers = _login(client, email_sender)
        _stream(client, token)
        first = client.get("/api/v1/analytics/daily", headers=headers).json()
        _stream(client, token)  # new data after snapshot exists
        second = client.get("/api/v1/analytics/daily", headers=headers).json()
        assert first["metrics"]["sample_count"] == second["metrics"]["sample_count"]

    def test_weekly_monthly_work(self, client, email_sender):
        token, headers = _login(client, email_sender)
        _stream(client, token)
        assert client.get("/api/v1/analytics/weekly", headers=headers).status_code == 200
        assert client.get("/api/v1/analytics/monthly", headers=headers).status_code == 200

    def test_wellness_score_and_trend(self, client, email_sender):
        token, headers = _login(client, email_sender)
        _stream(client, token)
        first = client.get("/api/v1/analytics/wellness-score", headers=headers).json()
        assert 0 <= first["score"] <= 100
        assert first["trend"] == "stable"  # no previous score yet

        _stream(client, token, typing_speed=90.0, error_rate=0.0)
        second = client.get("/api/v1/analytics/wellness-score", headers=headers).json()
        assert second["delta"] is not None

    def test_burnout_risk_includes_contributing_factors(self, client, email_sender):
        token, headers = _login(client, email_sender)
        _stream(client, token, error_rate=0.3)
        resp = client.get("/api/v1/analytics/burnout-risk", headers=headers).json()
        assert resp["level"] in {"low", "moderate", "high"}
        assert "stressed_ratio" in resp["contributing_factors"]

    def test_requires_auth(self, client, email_sender):
        assert client.get("/api/v1/analytics/wellness-score").status_code == 401
