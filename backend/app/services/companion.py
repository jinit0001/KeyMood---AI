"""Module 10: AI Companion (rule-based chat with crisis-aware escalation).

Honesty-by-design, same as every other module:
- The reply generator is a rule-based keyword/mood router, NOT a trained LLM.
  `CompanionReplyEngine` is written as its own small class specifically so a
  real LLM call can be swapped in later behind the same interface
  (`generate(mood, text) -> str`) without touching the service or API layer.
- Crisis detection is a conservative keyword match. On a match, the service
  does not try to handle the situation itself -- it calls out to the SOS
  module's existing risk-escalation path (Module 4) through the
  `RiskEscalator` Protocol below, so there is exactly one place in the whole
  system that ever creates a risk event. Wire `RiskEscalator` to your real
  `SosService` (see INTEGRATION_README.md) -- this module intentionally does
  not reimplement escalation logic.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError

MAX_MESSAGE_LENGTH = 2000

# Conservative, intentionally small keyword list for a documented, auditable
# trigger -- expanding this is a future-work item, not something to hide
# behind a vague "AI detects distress" claim.
CRISIS_KEYWORDS = (
    "kill myself", "suicide", "end my life", "want to die",
    "hurt myself", "self harm", "no reason to live",
)

MOOD_REPLIES = {
    "stressed": "It sounds like things feel like a lot right now. Want to take a slow breath with me, or talk through what's weighing on you?",
    "tired": "You sound worn out. Even five minutes away from the screen can help -- is there something small you could rest from right now?",
    "calm": "Good to hear you're feeling steady. Anything on your mind you'd like to note down in your journal while it's fresh?",
    "focused": "You seem in a good flow. I'll stay quiet unless you need me -- just say the word.",
    "happy": "Love that energy. Want to jot down what's going well today, for a future you to look back on?",
    None: "I'm here. Tell me a bit about how you're doing right now.",
}


class SessionNotFoundError(NotFoundError):
    error_code = "COMPANION_SESSION_NOT_FOUND"


@dataclass
class ChatSession:
    id: UUID
    user_id: UUID
    created_at: datetime


@dataclass
class ChatMessage:
    id: UUID
    session_id: UUID
    role: str  # "user" | "companion"
    content: str
    flagged_crisis: bool
    created_at: datetime


class ChatSessionRepository(Protocol):
    def get_or_create(self, user_id: UUID) -> ChatSession: ...
    def get(self, session_id: UUID) -> ChatSession | None: ...


class ChatMessageRepository(Protocol):
    def add(self, session_id: UUID, role: str, content: str, flagged_crisis: bool) -> ChatMessage: ...
    def list_for_session(self, session_id: UUID, limit: int = 50) -> list[ChatMessage]: ...


class MoodProvider(Protocol):
    """Adapter onto Module 3 (Emotion) -- return the user's latest known mood label, or None."""
    def latest_mood(self, user_id: UUID) -> str | None: ...


class RiskEscalator(Protocol):
    """Adapter onto Module 4 (SOS) -- the ONLY path by which this module ever raises a risk event."""
    def trigger(self, user_id: UUID, note: str) -> None: ...


def _is_crisis(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in CRISIS_KEYWORDS)


class CompanionReplyEngine:
    """Deliberately simple and swappable -- see module docstring."""

    def generate(self, mood: str | None, user_text: str) -> str:
        if _is_crisis(user_text):
            return (
                "I'm concerned about what you just shared, and I don't want you to go through this alone. "
                "I've flagged this so you'll be offered a check-in and the option to reach your trusted contacts. "
                "If you're in immediate danger, please contact a local emergency or crisis line right now."
            )
        return MOOD_REPLIES.get(mood, MOOD_REPLIES[None])


class AICompanionService:
    def __init__(
        self,
        sessions: ChatSessionRepository,
        messages: ChatMessageRepository,
        mood_provider: MoodProvider,
        escalator: RiskEscalator,
        reply_engine: CompanionReplyEngine | None = None,
    ) -> None:
        self._sessions = sessions
        self._messages = messages
        self._mood = mood_provider
        self._escalator = escalator
        self._engine = reply_engine or CompanionReplyEngine()

    def get_or_create_session(self, user_id: UUID) -> ChatSession:
        return self._sessions.get_or_create(user_id)

    def history(self, user_id: UUID, limit: int = 50) -> list[ChatMessage]:
        session = self._sessions.get_or_create(user_id)
        return self._messages.list_for_session(session.id, limit)

    def send_message(self, user_id: UUID, text: str) -> ChatMessage:
        text = (text or "").strip()
        if not text:
            raise ValidationError("Message cannot be empty")
        if len(text) > MAX_MESSAGE_LENGTH:
            raise ValidationError(f"Message exceeds {MAX_MESSAGE_LENGTH} characters")

        session = self._sessions.get_or_create(user_id)
        crisis = _is_crisis(text)
        self._messages.add(session.id, "user", text, crisis)

        if crisis:
            # Single, auditable escalation path -- Module 4 owns what happens next
            # (guardian consent, notification) exactly as it does for /sos/trigger.
            self._escalator.trigger(user_id, note="Crisis-level language detected by AI Companion")

        mood = self._mood.latest_mood(user_id)
        reply_text = self._engine.generate(mood, text)
        return self._messages.add(session.id, "companion", reply_text, crisis)
