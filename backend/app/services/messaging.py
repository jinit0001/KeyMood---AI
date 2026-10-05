"""Module 9: Messaging (1:1 and group chat).

Design notes / documented gaps:
- Presence of a WebSocket connection registry is in-memory and single-process
  (see app/api/v1/messaging.py). This will not scale past one app instance;
  a real deployment needs Redis pub/sub. Documented here deliberately rather
  than silently shipped as "production ready".
- media_attachments table exists only so `media_id` has something to point
  at (per DATABASE.md parity) - there is no upload endpoint in this module.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError

MAX_CONTENT_LENGTH = 4000


class NotAMemberError(ForbiddenError):
    error_code = "NOT_A_MEMBER"


class NotFriendsError(ForbiddenError):
    error_code = "NOT_FRIENDS"


class ConversationNotFoundError(NotFoundError):
    error_code = "CONVERSATION_NOT_FOUND"


@dataclass
class Conversation:
    id: UUID
    type: str  # "direct" | "group"
    title: str | None
    created_by: UUID
    created_at: datetime


@dataclass
class ConversationMember:
    id: UUID
    conversation_id: UUID
    user_id: UUID
    role: str  # "member" | "admin"
    joined_at: datetime
    left_at: datetime | None = None


@dataclass
class Message:
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    content: str
    media_id: UUID | None
    created_at: datetime
    deleted_at: datetime | None = None


class ConversationRepository(Protocol):
    def create(self, type_: str, title: str | None, created_by: UUID) -> Conversation: ...
    def get(self, conversation_id: UUID) -> Conversation | None: ...


class ConversationMemberRepository(Protocol):
    def add(self, conversation_id: UUID, user_id: UUID, role: str) -> ConversationMember: ...
    def get(self, conversation_id: UUID, user_id: UUID) -> ConversationMember | None: ...
    def list_members(self, conversation_id: UUID) -> list[ConversationMember]: ...


class MessageRepository(Protocol):
    def create(self, conversation_id: UUID, sender_id: UUID, content: str, media_id: UUID | None) -> Message: ...
    def list_page(self, conversation_id: UUID, before: UUID | None, limit: int) -> tuple[list[Message], bool]: ...
    def get(self, message_id: UUID) -> Message | None: ...


class MessageReadRepository(Protocol):
    def mark_read(self, message_id: UUID, user_id: UUID) -> None: ...


class FriendshipChecker(Protocol):
    def are_friends(self, user_a: UUID, user_b: UUID) -> bool: ...


def _normalize(a: UUID, b: UUID) -> tuple[UUID, UUID]:
    return (a, b) if str(a) < str(b) else (b, a)


class MessagingService:
    def __init__(
        self,
        conversations: ConversationRepository,
        members: ConversationMemberRepository,
        messages: MessageRepository,
        reads: MessageReadRepository,
        friendships: FriendshipChecker,
    ) -> None:
        self._conversations = conversations
        self._members = members
        self._messages = messages
        self._reads = reads
        self._friendships = friendships

    def create_conversation(
        self, creator_id: UUID, type_: str, member_ids: list[UUID], title: str | None = None
    ) -> Conversation:
        if type_ == "direct":
            if len(member_ids) != 1:
                raise ValidationError("Direct conversations require exactly one other member")
            other = member_ids[0]
            if not self._friendships.are_friends(creator_id, other):
                raise NotFriendsError("You can only message friends")
        elif type_ == "group":
            if not title:
                raise ValidationError("Group conversations require a title")
        else:
            raise ValidationError("type must be 'direct' or 'group'")

        conv = self._conversations.create(type_, title, creator_id)
        self._members.add(conv.id, creator_id, role="admin" if type_ == "group" else "member")
        for uid in member_ids:
            self._members.add(conv.id, uid, role="member")
        return conv

    def is_member(self, conversation_id: UUID, user_id: UUID) -> bool:
        return self._members.get(conversation_id, user_id) is not None

    def member_ids(self, conversation_id: UUID) -> list[UUID]:
        return [m.user_id for m in self._members.list_members(conversation_id)]

    def list_messages(
        self, user_id: UUID, conversation_id: UUID, before: UUID | None = None, limit: int = 50
    ) -> tuple[list[Message], bool]:
        if not self.is_member(conversation_id, user_id):
            raise NotAMemberError("You are not a member of this conversation")
        return self._messages.list_page(conversation_id, before, limit)

    def send_message(
        self, user_id: UUID, conversation_id: UUID, content: str, media_id: UUID | None = None
    ) -> Message:
        if not self.is_member(conversation_id, user_id):
            raise NotAMemberError("You are not a member of this conversation")
        content = (content or "").strip()
        if not content and not media_id:
            raise ValidationError("Message must have content or media")
        if len(content) > MAX_CONTENT_LENGTH:
            raise ValidationError(f"Message content exceeds {MAX_CONTENT_LENGTH} characters")
        return self._messages.create(conversation_id, user_id, content, media_id)

    def mark_read(self, user_id: UUID, message_id: UUID) -> None:
        self._reads.mark_read(message_id, user_id)
