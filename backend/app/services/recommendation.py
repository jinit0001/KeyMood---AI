from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID, uuid4

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.emotion import EmotionPredictionRepository

VALID_REACTIONS = {"accepted", "dismissed", "snoozed"}
ACTIVE_WINDOW_HOURS = 6  # not specified anywhere — gap-filled

# mood label -> [(type, title, description), ...]. Fixed, deterministic —
# NOT a learned/personalized engine. recommendation_feedback exists for
# exactly the learning this doesn't yet do.
_BY_MOOD: dict[str, list[tuple[str, str, str]]] = {
    "stressed": [("break", "Take a 5-minute break", "Step away from the screen."),
                 ("meditation", "Try a breathing exercise", "A short box-breathing session can help.")],
    "tired": [("break", "Take a proper break", "Step away for at least 15 minutes."),
              ("hydration", "Drink some water", "Dehydration is a common driver of fatigue.")],
    "focused": [("productivity", "Keep going", "You're in a strong focus window."),
                ("break", "Plan your next break", "Schedule one before focus fades.")],
    "happy": [("recovery", "Note what's working", "Worth remembering what helped."),
              ("music", "Keep the momentum", "A favorite playlist can sustain a good mood.")],
    "calm": [("productivity", "Good moment to plan", "A calm state is a good time to set a goal.")],
}
_DEFAULT = [("break", "Take a short break", "A quick pause can help reset focus.")]


class RecommendationNotFoundError(NotFoundError):
    error_code = "RECOMMENDATION_NOT_FOUND"


@dataclass
class Recommendation:
    id: UUID
    user_id: UUID
    type: str
    payload: dict
    created_at: datetime
    shown_at: datetime | None = None


@dataclass
class RecommendationFeedback:
    id: UUID
    recommendation_id: UUID
    user_id: UUID
    reaction: str
    created_at: datetime


class RecommendationRepository(Protocol):
    def add(self, r: Recommendation) -> None: ...
    def get_by_id(self, rid: UUID) -> Recommendation | None: ...
    def list_active_for_user(self, user_id: UUID, shown_after: datetime) -> list[Recommendation]: ...
    def list_with_feedback(self, user_id: UUID, ids: list[UUID]) -> set[UUID]: ...


class RecommendationFeedbackRepository(Protocol):
    def add(self, f: RecommendationFeedback) -> None: ...


class RecommendationService:
    def __init__(self, repo: RecommendationRepository, feedback: RecommendationFeedbackRepository,
                 emotion_predictions: EmotionPredictionRepository):
        self._repo, self._feedback, self._emotion = repo, feedback, emotion_predictions

    def get_current(self, user_id: UUID) -> list[Recommendation]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ACTIVE_WINDOW_HOURS)
        candidates = self._repo.list_active_for_user(user_id, cutoff)
        actioned = self._repo.list_with_feedback(user_id, [c.id for c in candidates])
        active = [c for c in candidates if c.id not in actioned]
        if active:
            return active

        latest = self._emotion.get_latest_for_user(user_id)
        mood = latest.label if latest else None
        now = datetime.now(timezone.utc)
        entries = _BY_MOOD.get(mood or "", _DEFAULT)
        created = []
        for rtype, title, desc in entries:
            rec = Recommendation(id=uuid4(), user_id=user_id, type=rtype,
                                  payload={"title": title, "description": desc}, created_at=now, shown_at=now)
            self._repo.add(rec)
            created.append(rec)
        return created

    def submit_feedback(self, user_id: UUID, recommendation_id: UUID, reaction: str) -> RecommendationFeedback:
        if reaction not in VALID_REACTIONS:
            raise ValidationError(f"reaction must be one of {sorted(VALID_REACTIONS)}.")
        rec = self._repo.get_by_id(recommendation_id)
        if rec is None or rec.user_id != user_id:
            raise RecommendationNotFoundError()
        f = RecommendationFeedback(id=uuid4(), recommendation_id=recommendation_id, user_id=user_id,
                                    reaction=reaction, created_at=datetime.now(timezone.utc))
        self._feedback.add(f)
        return f
