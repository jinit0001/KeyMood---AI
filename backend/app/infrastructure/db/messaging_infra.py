from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, select
from app.infrastructure.db.models.user_profile import UserProfileModel
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.infrastructure.db.base import Base
from app.services.messaging import Conversation, ConversationMember, Message


class MediaAttachmentModel(Base):
    __tablename__ = "media_attachments"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    uploader_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    storage_url: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ConversationModel(Base):
    __tablename__ = "conversations"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ConversationMemberModel(Base):
    __tablename__ = "conversation_members"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False, default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MessageModel(Base):
    __tablename__ = "messages"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    sender_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("media_attachments.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MessageReadModel(Base):
    __tablename__ = "message_reads"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    message_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("messages.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def _to_conv(m: ConversationModel) -> Conversation:
    return Conversation(id=m.id, type=m.type, title=m.title, created_by=m.created_by, created_at=m.created_at)


def _to_member(m: ConversationMemberModel) -> ConversationMember:
    return ConversationMember(
        id=m.id, conversation_id=m.conversation_id, user_id=m.user_id,
        role=m.role, joined_at=m.joined_at, left_at=m.left_at,
    )


def _to_message(m: MessageModel) -> Message:
    return Message(
        id=m.id, conversation_id=m.conversation_id, sender_id=m.sender_id,
        content=m.content, media_id=m.media_id, created_at=m.created_at, deleted_at=m.deleted_at,
    )


class SqlConversationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, type_: str, title: str | None, created_by: UUID) -> Conversation:
        row = ConversationModel(type=type_, title=title, created_by=created_by)
        self._db.add(row)
        self._db.flush()
        return _to_conv(row)

    def get(self, conversation_id: UUID) -> Conversation | None:
        row = self._db.get(ConversationModel, conversation_id)
        return _to_conv(row) if row else None


class SqlConversationMemberRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, conversation_id: UUID, user_id: UUID, role: str) -> ConversationMember:
        row = ConversationMemberModel(conversation_id=conversation_id, user_id=user_id, role=role)
        self._db.add(row)
        self._db.flush()
        return _to_member(row)

    def get(self, conversation_id: UUID, user_id: UUID) -> ConversationMember | None:
        row = self._db.execute(
            select(ConversationMemberModel).where(
                ConversationMemberModel.conversation_id == conversation_id,
                ConversationMemberModel.user_id == user_id,
                ConversationMemberModel.left_at.is_(None),
            )
        ).scalar_one_or_none()
        return _to_member(row) if row else None

    def list_members(self, conversation_id: UUID) -> list[ConversationMember]:
        rows = self._db.execute(
            select(ConversationMemberModel).where(
                ConversationMemberModel.conversation_id == conversation_id,
                ConversationMemberModel.left_at.is_(None),
            )
        ).scalars().all()
        return [_to_member(r) for r in rows]


class SqlMessageRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, conversation_id: UUID, sender_id: UUID, content: str, media_id: UUID | None) -> Message:
        row = MessageModel(conversation_id=conversation_id, sender_id=sender_id, content=content, media_id=media_id)
        self._db.add(row)
        self._db.flush()
        return _to_message(row)

    def list_page(self, conversation_id: UUID, before: UUID | None, limit: int) -> tuple[list[Message], bool]:
        q = select(MessageModel).where(MessageModel.conversation_id == conversation_id)
        if before is not None:
            before_row = self._db.get(MessageModel, before)
            if before_row is not None:
                q = q.where(MessageModel.created_at < before_row.created_at)
        q = q.order_by(MessageModel.created_at.desc()).limit(limit + 1)
        rows = self._db.execute(q).scalars().all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        return [_to_message(r) for r in rows], has_more

    def get(self, message_id: UUID) -> Message | None:
        row = self._db.get(MessageModel, message_id)
        return _to_message(row) if row else None


class SqlMessageReadRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def mark_read(self, message_id: UUID, user_id: UUID) -> None:
        existing = self._db.execute(
            select(MessageReadModel).where(
                MessageReadModel.message_id == message_id, MessageReadModel.user_id == user_id
            )
        ).scalar_one_or_none()
        if existing is None:
            self._db.add(MessageReadModel(message_id=message_id, user_id=user_id))
            self._db.flush()


class SqlConversationQuery:
    """Read-model for the conversation list (members' display names + last message).

    Kept separate from the repositories above: it is a query for the UI,
    not part of the domain service.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_user(self, user_id: UUID) -> list[dict]:
        conv_rows = self._db.execute(
            select(ConversationModel)
            .join(ConversationMemberModel, ConversationMemberModel.conversation_id == ConversationModel.id)
            .where(ConversationMemberModel.user_id == user_id, ConversationMemberModel.left_at.is_(None))
        ).scalars().all()
        out: list[dict] = []
        for conv in conv_rows:
            members = self._db.execute(
                select(ConversationMemberModel.user_id, UserProfileModel.display_name)
                .join(UserProfileModel, UserProfileModel.user_id == ConversationMemberModel.user_id, isouter=True)
                .where(ConversationMemberModel.conversation_id == conv.id, ConversationMemberModel.left_at.is_(None))
            ).all()
            last = self._db.execute(
                select(MessageModel)
                .where(MessageModel.conversation_id == conv.id, MessageModel.deleted_at.is_(None))
                .order_by(MessageModel.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            out.append({
                "id": conv.id,
                "type": conv.type,
                "title": conv.title,
                "created_at": conv.created_at,
                "members": [{"user_id": uid, "display_name": name or "Unknown"} for uid, name in members],
                "last_message": (
                    {"content": last.content, "sender_id": last.sender_id, "created_at": last.created_at}
                    if last else None
                ),
            })
        out.sort(key=lambda c: (c["last_message"]["created_at"] if c["last_message"] else c["created_at"]), reverse=True)
        return out
