import re
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_auth_service
from app.core.exceptions import GuardianNotFoundError, RiskEventNotFoundError, ValidationError
from app.core.security import jwt as jwt_utils
from app.domain.sos import EmergencyContact, Guardian, GuardianConsent, RiskEscalation, RiskEvent, SosNotification
from app.infrastructure.db.repositories.email_verification_repository import SqlEmailVerificationRepository
from app.infrastructure.db.repositories.oauth_identity_repository import SqlOAuthIdentityRepository
from app.infrastructure.db.repositories.password_reset_repository import SqlPasswordResetRepository
from app.infrastructure.db.repositories.profile_initializer import SqlProfileInitializer
from app.infrastructure.db.repositories.refresh_token_repository import SqlRefreshTokenRepository
from app.infrastructure.db.repositories.user_repository import SqlUserRepository
from app.infrastructure.db.session import get_db, get_session_factory
from app.main import app
from app.services.auth_service import AuthService
from app.services.sos import SosService
from tests.fakes import FakeAsyncRedis, FakeEmailSender, FakeGoogleOAuthProvider

VALID_PASSWORD = "Str0ng!Passw0rd"


# --- lean in-memory fakes, module-local since SOS is the only user ---
class _FakeRepo:
    def __init__(self): self._items = {}


class FakeContacts(_FakeRepo):
    def add(self, c): self._items[c.id] = c
    def get_by_id(self, cid): return self._items.get(cid)
    def list_for_user(self, uid): return [c for c in self._items.values() if c.user_id == uid]
    def delete(self, cid): self._items.pop(cid, None)


class FakeGuardians(_FakeRepo):
    def add(self, g): self._items[g.id] = g
    def get_by_id(self, gid): return self._items.get(gid)
    def list_for_user(self, uid): return [g for g in self._items.values() if g.user_id == uid]
    def delete(self, gid): self._items.pop(gid, None)


class FakeConsents(_FakeRepo):
    def add(self, c): self._items[c.guardian_id] = c
    def get_by_guardian_id(self, gid): return self._items.get(gid)
    def update_consent(self, gid, given, when):
        c = self._items.get(gid)
        if c:
            c.consent_given = given
            c.consented_at, c.revoked_at = (when, None) if given else (c.consented_at, when)


class FakeRiskEvents(_FakeRepo):
    def add(self, e): self._items[e.id] = e
    def get_by_id(self, eid): return self._items.get(eid)
    def list_for_user(self, uid): return [e for e in self._items.values() if e.user_id == uid]


class FakeEscalations:
    def __init__(self): self.items = []
    def add(self, e): self.items.append(e)
    def list_for_event(self, eid): return [e for e in self.items if e.risk_event_id == eid]


class FakeNotifications:
    def __init__(self): self.items = []
    def add(self, n): self.items.append(n)


def _service():
    return SosService(FakeContacts(), FakeGuardians(), FakeConsents(), FakeRiskEvents(), FakeEscalations(), FakeNotifications())


class TestSosServiceUnit:
    def test_invite_guardian_creates_pending_consent(self):
        svc = _service()
        g, token = svc.invite_guardian(uuid4(), "Dad", "+91987654321")
        assert token
        assert svc._consents.get_by_guardian_id(g.id).consent_given is False

    def test_confirm_consent_valid_token(self):
        svc = _service()
        g, token = svc.invite_guardian(uuid4(), "Dad", "+91987654321")
        svc.confirm_guardian_consent(g.id, token, True)
        assert svc._consents.get_by_guardian_id(g.id).consent_given is True

    def test_confirm_consent_wrong_guardian_id_rejected(self):
        svc = _service()
        _, token = svc.invite_guardian(uuid4(), "Dad", "+91987654321")
        with pytest.raises(jwt_utils.InvalidTokenError):
            svc.confirm_guardian_consent(uuid4(), token, True)

    def test_trigger_never_notifies_directly(self):
        svc = _service()
        user_id = uuid4()
        svc.invite_guardian(user_id, "Dad", "+91987654321")
        svc.trigger(user_id, "manual", {})
        assert svc._notifications.items == []

    def test_trigger_invalid_source_rejected(self):
        with pytest.raises(ValidationError):
            _service().trigger(uuid4(), "companion_chat", {})

    def test_confirm_notifies_only_consenting_guardians(self):
        svc = _service()
        user_id = uuid4()
        g1, t1 = svc.invite_guardian(user_id, "Dad", "+91987654321")
        svc.confirm_guardian_consent(g1.id, t1, True)
        svc.invite_guardian(user_id, "Uncle", "+91111111111")  # never confirms

        event, _ = svc.trigger(user_id, "manual", {})
        notifications = svc.confirm_escalation(user_id, event.id)
        assert len(notifications) == 1
        assert notifications[0].guardian_id == g1.id

    def test_confirm_someone_elses_event_raises(self):
        svc = _service()
        event, _ = svc.trigger(uuid4(), "manual", {})
        with pytest.raises(RiskEventNotFoundError):
            svc.confirm_escalation(uuid4(), event.id)

    def test_dismiss_does_not_notify(self):
        svc = _service()
        user_id = uuid4()
        svc.invite_guardian(user_id, "Dad", "+91987654321")
        event, _ = svc.trigger(user_id, "manual", {})
        svc.dismiss_escalation(user_id, event.id)
        assert svc._notifications.items == []
        actions = [e.action for e in svc._escalations.list_for_event(event.id)]
        assert "user_dismissed" in actions


# --- Real Postgres tests ---

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
    email = f"sos-{uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": VALID_PASSWORD, "display_name": "T"})
    token = _extract_token(email_sender, email)
    client.post("/api/v1/auth/verify-email", json={"token": token})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


class TestSosApiReal:
    def test_contact_and_guardian_flow(self, client, email_sender):
        headers = _login(client, email_sender)
        invite = client.post("/api/v1/sos/guardians", json={"name": "Dad", "phone": "+919876543210"}, headers=headers)
        assert invite.status_code == 201
        guardian_id, token = invite.json()["guardian"]["id"], invite.json()["consent_token"]

        # Consent is unauthenticated — no headers sent.
        consent_resp = client.post(f"/api/v1/sos/guardians/{guardian_id}/consent", json={"token": token, "consent_given": True})
        assert consent_resp.status_code == 204

    def test_trigger_confirm_notifies_end_to_end(self, client, email_sender):
        headers = _login(client, email_sender)
        invite = client.post("/api/v1/sos/guardians", json={"name": "Dad", "phone": "+919876543210"}, headers=headers)
        guardian_id, token = invite.json()["guardian"]["id"], invite.json()["consent_token"]
        client.post(f"/api/v1/sos/guardians/{guardian_id}/consent", json={"token": token, "consent_given": True})

        trigger = client.post("/api/v1/sos/trigger", json={"source": "manual", "context": {}}, headers=headers)
        assert trigger.json()["checkin_shown"] is True
        risk_event_id = trigger.json()["risk_event_id"]

        confirm = client.post(f"/api/v1/sos/escalations/{risk_event_id}/confirm", headers=headers)
        assert len(confirm.json()) == 1
        assert confirm.json()[0]["channel"] == "sms"

    def test_no_rate_limit_on_trigger(self, client, email_sender):
        headers = _login(client, email_sender)
        for _ in range(15):
            resp = client.post("/api/v1/sos/trigger", json={"source": "manual", "context": {}}, headers=headers)
            assert resp.status_code == 200

    def test_cannot_confirm_someone_elses_event(self, client, email_sender):
        headers_a = _login(client, email_sender)
        headers_b = _login(client, email_sender)
        trigger = client.post("/api/v1/sos/trigger", json={"source": "manual", "context": {}}, headers=headers_a)
        resp = client.post(f"/api/v1/sos/escalations/{trigger.json()['risk_event_id']}/confirm", headers=headers_b)
        assert resp.status_code == 404

    def test_append_only_enforcement_at_db_level(self, client, email_sender):
        """Not a service-layer test — a real UPDATE against the real DB,
        proving the BEFORE UPDATE trigger genuinely rejects it."""
        headers = _login(client, email_sender)
        trigger = client.post("/api/v1/sos/trigger", json={"source": "manual", "context": {}}, headers=headers)
        risk_event_id = trigger.json()["risk_event_id"]

        db = get_session_factory()()
        try:
            with pytest.raises(Exception, match="append-only"):
                db.execute(text("UPDATE risk_events SET risk_level = 'high' WHERE id = :id"), {"id": risk_event_id})
                db.flush()
        finally:
            db.rollback()
            db.close()
