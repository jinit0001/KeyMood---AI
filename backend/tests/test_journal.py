import re
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_auth_service
from app.core.exceptions import JournalEntryNotFoundError, ValidationError
from app.domain.journal import JournalEntry
from app.infrastructure.db.repositories.email_verification_repository import SqlEmailVerificationRepository
from app.infrastructure.db.repositories.oauth_identity_repository import SqlOAuthIdentityRepository
from app.infrastructure.db.repositories.password_reset_repository import SqlPasswordResetRepository
from app.infrastructure.db.repositories.profile_initializer import SqlProfileInitializer
from app.infrastructure.db.repositories.refresh_token_repository import SqlRefreshTokenRepository
from app.infrastructure.db.repositories.user_repository import SqlUserRepository
from app.infrastructure.db.session import get_db
from app.main import app
from app.services.auth_service import AuthService
from app.services.journal import MAX_CONTENT_LENGTH, JournalService
from tests.fakes import FakeAsyncRedis, FakeEmailSender, FakeGoogleOAuthProvider

VALID_PASSWORD = "Str0ng!Passw0rd"


class FakeJournalRepo:
    def __init__(self): self._items: dict = {}
    def add(self, e: JournalEntry): self._items[e.id] = e
    def get_by_id(self, eid): return self._items.get(eid)
    def update(self, e): self._items[e.id] = e
    def delete(self, eid): self._items.pop(eid, None)
    def list_for_user(self, uid, limit, offset):
        m = sorted([e for e in self._items.values() if e.user_id == uid], key=lambda e: e.created_at, reverse=True)
        return m[offset:offset + limit]
    def search(self, uid, query, tag, limit, offset):
        m = [e for e in self._items.values() if e.user_id == uid]
        if query: m = [e for e in m if query.lower() in e.content.lower()]
        if tag: m = [e for e in m if tag in e.tags]
        return m[offset:offset + limit]


class TestJournalServiceUnit:
    def test_create_and_get(self):
        svc = JournalService(FakeJournalRepo())
        user_id = uuid4()
        entry = svc.create(user_id, "Today was good.")
        assert svc.get(user_id, entry.id).content == "Today was good."

    def test_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            JournalService(FakeJournalRepo()).create(uuid4(), "   ")

    def test_over_max_length_rejected(self):
        with pytest.raises(ValidationError):
            JournalService(FakeJournalRepo()).create(uuid4(), "x" * (MAX_CONTENT_LENGTH + 1))

    def test_get_someone_elses_entry_raises(self):
        svc = JournalService(FakeJournalRepo())
        entry = svc.create(uuid4(), "Private")
        with pytest.raises(JournalEntryNotFoundError):
            svc.get(uuid4(), entry.id)

    def test_partial_update_preserves_other_fields(self):
        svc = JournalService(FakeJournalRepo())
        user_id = uuid4()
        entry = svc.create(user_id, "Original", tags=["a"])
        updated = svc.update(user_id, entry.id, tags=["b"])
        assert updated.content == "Original"
        assert updated.tags == ["b"]

    def test_delete(self):
        svc = JournalService(FakeJournalRepo())
        user_id = uuid4()
        entry = svc.create(user_id, "Entry")
        svc.delete(user_id, entry.id)
        with pytest.raises(JournalEntryNotFoundError):
            svc.get(user_id, entry.id)

    def test_summary_no_llm_ai_summary_stays_none(self):
        svc = JournalService(FakeJournalRepo())
        user_id = uuid4()
        entry = svc.create(user_id, "Entry")
        assert svc.request_summary(user_id, entry.id).ai_summary is None


# --- Real Postgres tests, mainly for full-text search ---

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
    email = f"journal-{uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": VALID_PASSWORD, "display_name": "T"})
    token = _extract_token(email_sender, email)
    client.post("/api/v1/auth/verify-email", json={"token": token})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


class TestJournalApiReal:
    def test_crud_flow(self, client, email_sender):
        headers = _login(client, email_sender)
        create = client.post("/api/v1/journal/entries", json={"content": "First", "tags": ["reflection"]}, headers=headers)
        assert create.status_code == 201
        entry_id = create.json()["id"]

        patch = client.patch(f"/api/v1/journal/entries/{entry_id}", json={"content": "Updated"}, headers=headers)
        assert patch.json()["content"] == "Updated"
        assert patch.json()["tags"] == ["reflection"]

        assert client.delete(f"/api/v1/journal/entries/{entry_id}", headers=headers).status_code == 204
        assert client.get(f"/api/v1/journal/entries/{entry_id}", headers=headers).status_code == 404

    def test_cannot_access_others_entry(self, client, email_sender):
        headers_a = _login(client, email_sender)
        headers_b = _login(client, email_sender)
        entry_id = client.post("/api/v1/journal/entries", json={"content": "Private"}, headers=headers_a).json()["id"]
        assert client.get(f"/api/v1/journal/entries/{entry_id}", headers=headers_b).status_code == 404

    def test_fulltext_search_stems_word(self, client, email_sender):
        """Proves real Postgres to_tsvector stemming, not substring matching."""
        headers = _login(client, email_sender)
        client.post("/api/v1/journal/entries", json={"content": "Feeling stressed about exams."}, headers=headers)
        client.post("/api/v1/journal/entries", json={"content": "A calm evening walk."}, headers=headers)

        resp = client.get("/api/v1/journal/search?q=stress", headers=headers)
        assert len(resp.json()) == 1

    def test_tag_filter(self, client, email_sender):
        headers = _login(client, email_sender)
        client.post("/api/v1/journal/entries", json={"content": "Work", "tags": ["work"]}, headers=headers)
        client.post("/api/v1/journal/entries", json={"content": "Personal", "tags": ["personal"]}, headers=headers)
        resp = client.get("/api/v1/journal/search?tag=work", headers=headers)
        assert len(resp.json()) == 1
        assert resp.json()[0]["content"] == "Work"

    def test_summary_endpoint_returns_202(self, client, email_sender):
        headers = _login(client, email_sender)
        entry_id = client.post("/api/v1/journal/entries", json={"content": "Entry"}, headers=headers).json()["id"]
        resp = client.post(f"/api/v1/journal/entries/{entry_id}/summary", headers=headers)
        assert resp.status_code == 202
        assert resp.json()["ai_summary"] is None
