import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, and_, func, or_, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session as DbSession, mapped_column

from app.infrastructure.db.base import Base
from app.services.social import Friendship, FriendRequest


class FriendshipModel(Base):
    __tablename__ = "friendships"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id_a: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    user_id_b: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FriendRequestModel(Base):
    __tablename__ = "friend_requests"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    receiver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SqlFriendshipRepository:
    def __init__(self, db: DbSession): self._db = db

    def add(self, f: Friendship) -> None:
        self._db.add(FriendshipModel(id=f.id, user_id_a=f.user_id_a, user_id_b=f.user_id_b))
        self._db.flush()

    def exists(self, user_a, user_b) -> bool:
        stmt = select(FriendshipModel).where(FriendshipModel.user_id_a == user_a, FriendshipModel.user_id_b == user_b)
        return self._db.execute(stmt).scalar_one_or_none() is not None

    def list_for_user(self, user_id, limit, offset) -> list[Friendship]:
        stmt = select(FriendshipModel).where(
            or_(FriendshipModel.user_id_a == user_id, FriendshipModel.user_id_b == user_id)
        ).order_by(FriendshipModel.created_at.desc()).limit(limit).offset(offset)
        return [Friendship(id=r.id, user_id_a=r.user_id_a, user_id_b=r.user_id_b, created_at=r.created_at)
                for r in self._db.execute(stmt).scalars().all()]

    def delete(self, user_a, user_b) -> None:
        stmt = select(FriendshipModel).where(FriendshipModel.user_id_a == user_a, FriendshipModel.user_id_b == user_b)
        row = self._db.execute(stmt).scalar_one_or_none()
        if row:
            self._db.delete(row)
            self._db.flush()


class SqlFriendRequestRepository:
    def __init__(self, db: DbSession): self._db = db

    def _to_domain(self, r: FriendRequestModel) -> FriendRequest:
        return FriendRequest(id=r.id, sender_id=r.sender_id, receiver_id=r.receiver_id, status=r.status,
                              created_at=r.created_at, responded_at=r.responded_at)

    def add(self, r: FriendRequest) -> None:
        self._db.add(FriendRequestModel(id=r.id, sender_id=r.sender_id, receiver_id=r.receiver_id, status=r.status))
        self._db.flush()

    def get_by_id(self, request_id) -> FriendRequest | None:
        row = self._db.get(FriendRequestModel, request_id)
        return self._to_domain(row) if row else None

    def get_pending_between(self, sender_id, receiver_id) -> FriendRequest | None:
        stmt = select(FriendRequestModel).where(FriendRequestModel.sender_id == sender_id,
                                                 FriendRequestModel.receiver_id == receiver_id,
                                                 FriendRequestModel.status == "pending")
        row = self._db.execute(stmt).scalar_one_or_none()
        return self._to_domain(row) if row else None

    def update(self, r: FriendRequest) -> None:
        row = self._db.get(FriendRequestModel, r.id)
        row.status, row.responded_at = r.status, r.responded_at
        self._db.flush()

    def list_for_user(self, user_id, status) -> list[FriendRequest]:
        conditions = [or_(FriendRequestModel.sender_id == user_id, FriendRequestModel.receiver_id == user_id)]
        if status:
            conditions.append(FriendRequestModel.status == status)
        stmt = select(FriendRequestModel).where(and_(*conditions)).order_by(FriendRequestModel.created_at.desc())
        return [self._to_domain(r) for r in self._db.execute(stmt).scalars().all()]
