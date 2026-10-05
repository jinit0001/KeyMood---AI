import re
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_auth_service
from app.core.exceptions import ValidationError
from app.domain.auth.entities import User, UserRole, UserStatus
from app.infrastructure.db.repositories.email_verification_repository import SqlEmailVerificationRepository
from app.infrastructure.db.repositories.oauth_identity_repository import SqlOAuthIdentityRepository
from app.infrastructure.db.repositories.password_reset_repository import SqlPasswordResetRepository
from app.infrastructure.db.repositories.profile_initializer import SqlProfileInitializer
from app.infrastructure.db.repositories.refresh_token_repository import SqlRefreshTokenRepository
from app.infrastructure.db.repositories.user_repository import SqlUserRepository
from app.infrastructure.db.session import get_db
from app.main import app
from app.services.auth_service import AuthService
from app.services.social import FriendRequestNotFoundError, Friendship, FriendRequest, SocialService
from tests.fakes import FakeAsyncRedis, FakeEmailSender, FakeGoogleOAuthProvider

VALID_PASSWORD = "Str0ng!Passw0rd"


class FakeFriendships:
    def __init__(self): self._items: dict = {}
    def add(self, f): self._items[(f.user_id_a, f.user_id_b)] = f
    def exists(self, a, b): return (a, b) in self._items
    def list_for_user(self, uid, limit, offset):
        m = [f for f in self._items.values() if f.user_id_a == uid or f.user_id_b == uid]
        return m[offset:offset + limit]
    def delete(self, a, b): self._items.pop((a, b), None)


class FakeRequests:
    def __init__(self): self._items: dict = {}
    def add(self, r): self._items[r.id] = r
    def get_by_id(self, rid): return self._items.get(rid)
    def get_pending_between(self, sender, receiver):
        for r in self._items.values():
            if r.sender_id == sender and r.receiver_id == receiver and r.status == "pending":
                return r
        return None
    def update(self, r): self._items[r.id] = r
    def list_for_user(self, uid, status):
        m = [r for r in self._items.values() if r.sender_id == uid or r.receiver_id == uid]
        return [r for r in m if status is None or r.status == status]


def _service():
    return SocialService(FakeFriendships(), FakeRequests())


class TestSocialServiceUnit:
    def test_send_request_creates_pending(self):
        svc = _service()
        r = svc.send_request(uuid4(), uuid4())
        assert r.status == "pending"

    def test_cannot_request_self(self):
        uid = uuid4()
        with pytest.raises(ValidationError):
            _service().send_request(uid, uid)

    def test_duplicate_pending_rejected(self):
        svc = _service()
        a, b = uuid4(), uuid4()
        svc.send_request(a, b)
        with pytest.raises(ValidationError):
            svc.send_request(a, b)

    def test_reverse_pending_also_rejected(self):
        svc = _service()
        a, b = uuid4(), uuid4()
        svc.send_request(a, b)
        with pytest.raises(ValidationError):
            svc.send_request(b, a)

    def test_accept_creates_friendship_normalized_order(self):
        svc = _service()
        a, b = uuid4(), uuid4()
        req = svc.send_request(a, b)
        friendship = svc.accept(b, req.id)
        assert str(friendship.user_id_a) < str(friendship.user_id_b)

    def test_accept_by_non_receiver_raises(self):
        svc = _service()
        a, b = uuid4(), uuid4()
        req = svc.send_request(a, b)
        with pytest.raises(FriendRequestNotFoundError):
            svc.accept(a, req.id)  # sender, not receiver

    def test_already_friends_cannot_request_again(self):
        svc = _service()
        a, b = uuid4(), uuid4()
        req = svc.send_request(a, b)
        svc.accept(b, req.id)
        with pytest.raises(ValidationError):
            svc.send_request(a, b)

    def test_decline_does_not_create_friendship(self):
        svc = _service()
        a, b = uuid4(), uuid4()
        req = svc.send_request(a, b)
        svc.decline(b, req.id)
        assert svc.list_friends(a) == []

    def test_list_friends_returns_other_party(self):
        svc = _service()
        a, b = uuid4(), uuid4()
        req = svc.send_request(a, b)
        svc.accept(b, req.id)
        assert svc.list_friends(a) == [b]
        assert svc.list_friends(b) == [a]


# --- Real Postgres + presence WebSocket ---

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
    email = f"social-{uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": VALID_PASSWORD, "display_name": "T"})
    token = _extract_token(email_sender, email)
    client.post("/api/v1/auth/verify-email", json={"token": token})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})
    body = resp.json()
    return body["access_token"], {"Authorization": f"Bearer {body['access_token']}"}


class TestSocialApiReal:
    def test_request_accept_friend_flow(self, client, email_sender):
        token_a, headers_a = _login(client, email_sender)
        token_b, headers_b = _login(client, email_sender)
        me_a = client.get("/api/v1/profile/me", headers=headers_a).json()
        receiver_id = me_a["user_id"]

        # b sends request to a
        send = client.post("/api/v1/social/requests", json={"receiver_id": receiver_id}, headers=headers_b)
        assert send.status_code == 201
        request_id = send.json()["id"]

        accept = client.post(f"/api/v1/social/requests/{request_id}/accept", headers=headers_a)
        assert accept.status_code == 200

        friends_a = client.get("/api/v1/social/friends", headers=headers_a).json()
        assert len(friends_a) == 1

    def test_duplicate_request_rejected_with_400(self, client, email_sender):
        _, headers_a = _login(client, email_sender)
        _, headers_b = _login(client, email_sender)
        receiver_id = client.get("/api/v1/profile/me", headers=headers_a).json()["user_id"]
        client.post("/api/v1/social/requests", json={"receiver_id": receiver_id}, headers=headers_b)
        resp = client.post("/api/v1/social/requests", json={"receiver_id": receiver_id}, headers=headers_b)
        assert resp.status_code == 400

    def test_remove_friend(self, client, email_sender):
        _, headers_a = _login(client, email_sender)
        _, headers_b = _login(client, email_sender)
        receiver_id = client.get("/api/v1/profile/me", headers=headers_a).json()["user_id"]
        req_id = client.post("/api/v1/social/requests", json={"receiver_id": receiver_id}, headers=headers_b).json()["id"]
        client.post(f"/api/v1/social/requests/{req_id}/accept", headers=headers_a)

        friend_id = client.get("/api/v1/social/friends", headers=headers_a).json()[0]
        assert client.delete(f"/api/v1/social/friends/{friend_id}", headers=headers_a).status_code == 204
        assert client.get("/api/v1/social/friends", headers=headers_a).json() == []

    def test_requires_auth(self, client, email_sender):
        assert client.get("/api/v1/social/friends").status_code == 401

    def test_presence_broadcasts_friend_online(self, client, email_sender):
        token_a, headers_a = _login(client, email_sender)
        token_b, headers_b = _login(client, email_sender)
        receiver_id = client.get("/api/v1/profile/me", headers=headers_a).json()["user_id"]
        req_id = client.post("/api/v1/social/requests", json={"receiver_id": receiver_id}, headers=headers_b).json()["id"]
        client.post(f"/api/v1/social/requests/{req_id}/accept", headers=headers_a)

        with client.websocket_connect(f"/api/v1/social/presence?token={token_a}") as ws_a:
            ws_a.receive_json()  # initial online_friends snapshot
            with client.websocket_connect(f"/api/v1/social/presence?token={token_b}") as ws_b:
                ws_b.receive_json()  # b's own snapshot
                event = ws_a.receive_json()  # a should be notified b came online
                assert event["event"] == "friend_online"
