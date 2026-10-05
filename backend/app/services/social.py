from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from app.core.exceptions import NotFoundError, ValidationError

VALID_STATUSES = {"pending", "accepted", "declined", "cancelled"}


class FriendRequestNotFoundError(NotFoundError):
    error_code = "FRIEND_REQUEST_NOT_FOUND"


@dataclass
class Friendship:
    id: UUID
    user_id_a: UUID
    user_id_b: UUID
    created_at: datetime


@dataclass
class FriendRequest:
    id: UUID
    sender_id: UUID
    receiver_id: UUID
    status: str
    created_at: datetime
    responded_at: datetime | None = None


class FriendshipRepository(Protocol):
    def add(self, f: Friendship) -> None: ...
    def exists(self, user_a: UUID, user_b: UUID) -> bool: ...
    def list_for_user(self, user_id: UUID, limit: int, offset: int) -> list[Friendship]: ...
    def delete(self, user_a: UUID, user_b: UUID) -> None: ...


class FriendRequestRepository(Protocol):
    def add(self, r: FriendRequest) -> None: ...
    def get_by_id(self, request_id: UUID) -> FriendRequest | None: ...
    def get_pending_between(self, sender_id: UUID, receiver_id: UUID) -> FriendRequest | None: ...
    def update(self, r: FriendRequest) -> None: ...
    def list_for_user(self, user_id: UUID, status: str | None) -> list[FriendRequest]: ...


def _normalize(a: UUID, b: UUID) -> tuple[UUID, UUID]:
    """friendships.user_id_a < user_id_b, per DATABASE.md's CHECK constraint."""
    return (a, b) if str(a) < str(b) else (b, a)


class SocialService:
    def __init__(self, friendships: FriendshipRepository, requests: FriendRequestRepository):
        self._friendships, self._requests = friendships, requests

    def list_friends(self, user_id: UUID, limit: int = 20, offset: int = 0) -> list[UUID]:
        friendships = self._friendships.list_for_user(user_id, min(max(limit, 1), 100), offset)
        return [f.user_id_b if f.user_id_a == user_id else f.user_id_a for f in friendships]

    def remove_friend(self, user_id: UUID, friend_id: UUID) -> None:
        a, b = _normalize(user_id, friend_id)
        self._friendships.delete(a, b)

    def send_request(self, sender_id: UUID, receiver_id: UUID) -> FriendRequest:
        if sender_id == receiver_id:
            raise ValidationError("Cannot send a friend request to yourself.")
        a, b = _normalize(sender_id, receiver_id)
        if self._friendships.exists(a, b):
            raise ValidationError("Already friends.")
        if self._requests.get_pending_between(sender_id, receiver_id) or self._requests.get_pending_between(receiver_id, sender_id):
            raise ValidationError("A pending request already exists between these users.")

        req = FriendRequest(id=uuid4(), sender_id=sender_id, receiver_id=receiver_id,
                             status="pending", created_at=datetime.now(timezone.utc))
        self._requests.add(req)
        return req

    def list_requests(self, user_id: UUID, status: str | None = None) -> list[FriendRequest]:
        if status is not None and status not in VALID_STATUSES:
            raise ValidationError(f"status must be one of {sorted(VALID_STATUSES)}.")
        return self._requests.list_for_user(user_id, status)

    def accept(self, user_id: UUID, request_id: UUID) -> Friendship:
        req = self._requests.get_by_id(request_id)
        if req is None or req.receiver_id != user_id or req.status != "pending":
            raise FriendRequestNotFoundError()
        req.status, req.responded_at = "accepted", datetime.now(timezone.utc)
        self._requests.update(req)

        a, b = _normalize(req.sender_id, req.receiver_id)
        friendship = Friendship(id=uuid4(), user_id_a=a, user_id_b=b, created_at=datetime.now(timezone.utc))
        self._friendships.add(friendship)
        return friendship

    def decline(self, user_id: UUID, request_id: UUID) -> FriendRequest:
        req = self._requests.get_by_id(request_id)
        if req is None or req.receiver_id != user_id or req.status != "pending":
            raise FriendRequestNotFoundError()
        req.status, req.responded_at = "declined", datetime.now(timezone.utc)
        self._requests.update(req)
        return req
