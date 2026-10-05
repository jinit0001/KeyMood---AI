from uuid import uuid4
from datetime import datetime, timezone

import pytest

from app.services.companion import AICompanionService, ChatMessage, ChatSession, ValidationError


class FakeSessions:
    def __init__(self):
        self.rows = {}

    def get_or_create(self, user_id):
        for s in self.rows.values():
            if s.user_id == user_id:
                return s
        s = ChatSession(id=uuid4(), user_id=user_id, created_at=datetime.now(timezone.utc))
        self.rows[s.id] = s
        return s

    def get(self, session_id):
        return self.rows.get(session_id)


class FakeMessages:
    def __init__(self):
        self.rows = []

    def add(self, session_id, role, content, flagged_crisis):
        m = ChatMessage(id=uuid4(), session_id=session_id, role=role, content=content, flagged_crisis=flagged_crisis, created_at=datetime.now(timezone.utc))
        self.rows.append(m)
        return m

    def list_for_session(self, session_id, limit=50):
        return [m for m in self.rows if m.session_id == session_id][:limit]


class FakeMoodProvider:
    def __init__(self, mood=None):
        self.mood = mood

    def latest_mood(self, user_id):
        return self.mood


class FakeEscalator:
    def __init__(self):
        self.triggered = []

    def trigger(self, user_id, note):
        self.triggered.append((user_id, note))


def make_service(mood=None):
    escalator = FakeEscalator()
    svc = AICompanionService(FakeSessions(), FakeMessages(), FakeMoodProvider(mood), escalator)
    return svc, escalator


class TestAICompanionServiceUnit:
    def test_session_is_created_lazily_and_reused(self):
        svc, _ = make_service()
        user = uuid4()
        s1 = svc.get_or_create_session(user)
        s2 = svc.get_or_create_session(user)
        assert s1.id == s2.id

    def test_empty_message_rejected(self):
        svc, _ = make_service()
        with pytest.raises(ValidationError):
            svc.send_message(uuid4(), "   ")

    def test_over_length_message_rejected(self):
        svc, _ = make_service()
        with pytest.raises(ValidationError):
            svc.send_message(uuid4(), "x" * 2001)

    def test_normal_message_does_not_escalate(self):
        svc, escalator = make_service(mood="stressed")
        reply = svc.send_message(uuid4(), "work has been a lot lately")
        assert reply.role == "companion"
        assert reply.flagged_crisis is False
        assert escalator.triggered == []

    def test_crisis_keyword_triggers_escalation_exactly_once(self):
        svc, escalator = make_service()
        user = uuid4()
        reply = svc.send_message(user, "I don't want to be here, I want to end my life")
        assert reply.flagged_crisis is True
        assert len(escalator.triggered) == 1
        assert escalator.triggered[0][0] == user

    def test_reply_is_mood_aware(self):
        svc, _ = make_service(mood="happy")
        reply = svc.send_message(uuid4(), "had a great day")
        assert "great" not in reply.content  # it's a canned reply, not an echo
        assert reply.role == "companion"

    def test_history_returns_messages_in_order(self):
        svc, _ = make_service()
        user = uuid4()
        svc.send_message(user, "first message")
        svc.send_message(user, "second message")
        hist = svc.history(user)
        # user msg, companion reply, user msg, companion reply
        assert [m.content for m in hist][0] == "first message"
        assert len(hist) == 4


# --- Real-DB test sketch -----------------------------------------------
# Merge into the shared real-DB test module once real EmotionMoodAdapter /
# SosRiskAdapter are wired (see INTEGRATION_README.md):
#
# class TestCompanionApiReal:
#     def test_send_message_persists_and_replies(self, client, make_user): ...
#     def test_crisis_message_calls_real_sos_trigger(self, client, make_user):
#         # send a crisis-keyword message, then check a risk_event row exists
#         # for that user via Module 4's own repository/query, same pattern
#         # as test_sos.py's own trigger tests.
