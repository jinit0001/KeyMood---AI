"""
Module 9 tests. Unit tests use local fakes. The *Real classes assume the
same client/_auth_override/_login fixtures and tests/fakes.py helpers
(FakeAsyncRedis, FakeEmailSender, FakeGoogleOAuthProvider) already used by
every other real-DB test file in this project (test_social.py etc.) -
copy this file alongside them so those fixtures resolve.
"""
from uuid import uuid4

import pytest

from app.services.messaging import MessagingService, NotAMemberError, NotFriendsError, ValidationError


class FakeConversations:
    def __init__(self):
        self.rows = {}

    def create(self, type_, title, created_by):
        from app.services.messaging import Conversation
        from datetime import datetime, timezone
        conv = Conversation(id=uuid4(), type=type_, title=title, created_by=created_by, created_at=datetime.now(timezone.utc))
        self.rows[conv.id] = conv
        return conv

    def get(self, conversation_id):
        return self.rows.get(conversation_id)


class FakeMembers:
    def __init__(self):
        self.rows = []

    def add(self, conversation_id, user_id, role):
        from app.services.messaging import ConversationMember
        from datetime import datetime, timezone
        m = ConversationMember(id=uuid4(), conversation_id=conversation_id, user_id=user_id, role=role, joined_at=datetime.now(timezone.utc))
        self.rows.append(m)
        return m

    def get(self, conversation_id, user_id):
        for m in self.rows:
            if m.conversation_id == conversation_id and m.user_id == user_id and m.left_at is None:
                return m
        return None

    def list_members(self, conversation_id):
        return [m for m in self.rows if m.conversation_id == conversation_id and m.left_at is None]


class FakeMessages:
    def __init__(self):
        self.rows = []

    def create(self, conversation_id, sender_id, content, media_id):
        from app.services.messaging import Message
        from datetime import datetime, timezone
        msg = Message(id=uuid4(), conversation_id=conversation_id, sender_id=sender_id, content=content, media_id=media_id, created_at=datetime.now(timezone.utc))
        self.rows.append(msg)
        return msg

    def list_page(self, conversation_id, before, limit):
        rows = [m for m in self.rows if m.conversation_id == conversation_id]
        rows.sort(key=lambda m: m.created_at, reverse=True)
        return rows[:limit], len(rows) > limit

    def get(self, message_id):
        for m in self.rows:
            if m.id == message_id:
                return m
        return None


class FakeReads:
    def __init__(self):
        self.rows = set()

    def mark_read(self, message_id, user_id):
        self.rows.add((message_id, user_id))


class FakeFriendships:
    def __init__(self, pairs=None):
        self.pairs = pairs or set()

    def are_friends(self, a, b):
        return (a, b) in self.pairs or (b, a) in self.pairs


def make_service(friend_pairs=None):
    return MessagingService(FakeConversations(), FakeMembers(), FakeMessages(), FakeReads(), FakeFriendships(friend_pairs))


class TestMessagingServiceUnit:
    def test_direct_requires_exactly_one_other_member(self):
        svc = make_service()
        a = uuid4()
        with pytest.raises(ValidationError):
            svc.create_conversation(a, "direct", [])

    def test_direct_requires_friendship(self):
        svc = make_service()
        a, b = uuid4(), uuid4()
        with pytest.raises(NotFriendsError):
            svc.create_conversation(a, "direct", [b])

    def test_direct_with_friends_succeeds(self):
        a, b = uuid4(), uuid4()
        svc = make_service(friend_pairs={(a, b)})
        conv = svc.create_conversation(a, "direct", [b])
        assert svc.is_member(conv.id, a)
        assert svc.is_member(conv.id, b)

    def test_group_requires_title(self):
        svc = make_service()
        a, b = uuid4(), uuid4()
        with pytest.raises(ValidationError):
            svc.create_conversation(a, "group", [b])

    def test_group_with_title_succeeds(self):
        svc = make_service()
        a, b, c = uuid4(), uuid4(), uuid4()
        conv = svc.create_conversation(a, "group", [b, c], title="Study Group")
        assert len(svc.member_ids(conv.id)) == 3

    def test_non_member_cannot_send(self):
        a, b, outsider = uuid4(), uuid4(), uuid4()
        svc = make_service(friend_pairs={(a, b)})
        conv = svc.create_conversation(a, "direct", [b])
        with pytest.raises(NotAMemberError):
            svc.send_message(outsider, conv.id, "hi")

    def test_content_over_max_rejected(self):
        a, b = uuid4(), uuid4()
        svc = make_service(friend_pairs={(a, b)})
        conv = svc.create_conversation(a, "direct", [b])
        with pytest.raises(ValidationError):
            svc.send_message(a, conv.id, "x" * 4001)

    def test_empty_content_no_media_rejected(self):
        a, b = uuid4(), uuid4()
        svc = make_service(friend_pairs={(a, b)})
        conv = svc.create_conversation(a, "direct", [b])
        with pytest.raises(ValidationError):
            svc.send_message(a, conv.id, "")

    def test_member_can_send(self):
        a, b = uuid4(), uuid4()
        svc = make_service(friend_pairs={(a, b)})
        conv = svc.create_conversation(a, "direct", [b])
        msg = svc.send_message(a, conv.id, "hello")
        assert msg.content == "hello"


# --- Real-DB / real-WebSocket tests ---------------------------------------
# Paste these into the shared real-DB test module (reuse the project's
# existing `client`, `_auth_override`, `_login` fixtures from conftest /
# test_social.py) rather than running this class standalone, since it needs
# two real authenticated users and a running Postgres+Redis, matching the
# pattern in test_social.py's presence tests.
#
# class TestMessagingApiReal:
#     def test_direct_conversation_requires_friendship(self, client, make_user): ...  # expect 403
#     def test_direct_conversation_with_friends_and_rest_send(self, client, make_user): ...
#     def test_non_member_cannot_read_messages(self, client, make_user): ...  # expect 403
#     def test_group_conversation_with_title(self, client, make_user): ...
#     def test_ws_message_send_delivers_to_other_member_live(self, client, make_user):
#         # open two client.websocket_connect() blocks (user A, user B),
#         # B sends {"type": "message.send", ...}, assert A receives "message.new"
#     def test_ws_typing_update_broadcasts(self, client, make_user): ...
#     def test_ws_rejects_invalid_token(self, client): ...
