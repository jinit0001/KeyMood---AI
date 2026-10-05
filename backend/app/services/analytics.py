from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID, uuid4

from app.core.exceptions import ValidationError
from app.domain.emotion import EmotionPredictionRepository

VALID_PERIODS = {"daily", "weekly", "monthly"}
_LOOKBACK_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}
WELLNESS_WINDOW_DAYS = 7
_MOOD_SCORE = {"happy": 100, "focused": 85, "calm": 70, "tired": 40, "stressed": 20}
_NEGATIVE = {"stressed", "tired"}
BURNOUT_HIGH, BURNOUT_MODERATE = 0.5, 0.25
_LARGE_LIMIT = 10_000


class InvalidPeriodError(ValidationError):
    error_code = "INVALID_PERIOD"


@dataclass
class AnalyticsSnapshot:
    id: UUID
    user_id: UUID
    period: str
    period_start: date
    metrics: dict
    created_at: datetime


@dataclass
class WellnessScore:
    id: UUID
    user_id: UUID
    score: float
    contributing_factors: dict
    computed_at: datetime


class AnalyticsSnapshotRepository(Protocol):
    def get(self, user_id: UUID, period: str, period_start: date) -> AnalyticsSnapshot | None: ...
    def upsert(self, s: AnalyticsSnapshot) -> None: ...


class WellnessScoreRepository(Protocol):
    def add(self, s: WellnessScore) -> None: ...
    def get_previous(self, user_id: UUID, before: datetime) -> WellnessScore | None: ...


# --- pure computation functions, deterministic formulas, NOT ML ---

def compute_period_metrics(labels: list[str]) -> dict:
    if not labels:
        return {"sample_count": 0, "mood_distribution": {}, "average_wellness": None}
    counts = Counter(labels)
    avg = sum(_MOOD_SCORE.get(l, 50) for l in labels) / len(labels)
    return {"sample_count": len(labels), "mood_distribution": dict(counts), "average_wellness": round(avg, 1)}


def compute_wellness_score(labels: list[str]) -> tuple[float, dict]:
    if not labels:
        return 70.0, {"sample_count": 0, "note": "no recent data, neutral baseline"}
    avg = sum(_MOOD_SCORE.get(l, 50) for l in labels) / len(labels)
    return round(avg, 1), {"sample_count": len(labels), "mood_distribution": dict(Counter(labels))}


def compute_burnout_risk(labels: list[str]) -> tuple[str, dict]:
    if not labels:
        return "low", {"sample_count": 0, "stressed_ratio": 0.0, "tired_ratio": 0.0}
    total = len(labels)
    negative_ratio = sum(1 for l in labels if l in _NEGATIVE) / total
    level = "high" if negative_ratio >= BURNOUT_HIGH else "moderate" if negative_ratio >= BURNOUT_MODERATE else "low"
    return level, {"sample_count": total, "stressed_ratio": round(labels.count("stressed") / total, 2),
                   "tired_ratio": round(labels.count("tired") / total, 2)}


def period_start_for(period: str, reference: date | None = None) -> date:
    """Gap-filled: weekly = Monday of that week, monthly = 1st of month."""
    ref = reference or datetime.now().date()
    if period == "daily":
        return ref
    if period == "weekly":
        return ref - timedelta(days=ref.weekday())
    if period == "monthly":
        return ref.replace(day=1)
    raise ValueError(f"Unknown period: {period}")


class AnalyticsService:
    def __init__(self, snapshots: AnalyticsSnapshotRepository, wellness: WellnessScoreRepository,
                 emotion_predictions: EmotionPredictionRepository):
        self._snapshots, self._wellness, self._emotion = snapshots, wellness, emotion_predictions

    def get_period_snapshot(self, user_id: UUID, period: str) -> AnalyticsSnapshot:
        """Spec says 'reads from analytics_snapshots, not live-computed' — no
        scheduler exists, so this computes+caches on first request per period."""
        if period not in VALID_PERIODS:
            raise InvalidPeriodError(f"period must be one of {sorted(VALID_PERIODS)}.")
        period_start = period_start_for(period)
        existing = self._snapshots.get(user_id, period, period_start)
        if existing:
            return existing

        from_dt = datetime.now(timezone.utc) - timedelta(days=_LOOKBACK_DAYS[period])
        predictions = self._emotion.get_history(user_id, from_dt, None, _LARGE_LIMIT, 0)
        metrics = compute_period_metrics([p.label for p in predictions])
        snapshot = AnalyticsSnapshot(id=uuid4(), user_id=user_id, period=period, period_start=period_start,
                                      metrics=metrics, created_at=datetime.now(timezone.utc))
        self._snapshots.upsert(snapshot)
        return snapshot

    def get_wellness_score(self, user_id: UUID) -> tuple[WellnessScore, str, float | None]:
        from_dt = datetime.now(timezone.utc) - timedelta(days=WELLNESS_WINDOW_DAYS)
        predictions = self._emotion.get_history(user_id, from_dt, None, _LARGE_LIMIT, 0)
        value, factors = compute_wellness_score([p.label for p in predictions])
        now = datetime.now(timezone.utc)
        previous = self._wellness.get_previous(user_id, now)
        score = WellnessScore(id=uuid4(), user_id=user_id, score=value, contributing_factors=factors, computed_at=now)
        self._wellness.add(score)

        if previous is None:
            return score, "stable", None
        delta = round(value - previous.score, 1)
        trend = "improving" if delta > 2 else "declining" if delta < -2 else "stable"
        return score, trend, delta

    def get_burnout_risk(self, user_id: UUID) -> tuple[str, dict]:
        from_dt = datetime.now(timezone.utc) - timedelta(days=WELLNESS_WINDOW_DAYS)
        predictions = self._emotion.get_history(user_id, from_dt, None, _LARGE_LIMIT, 0)
        return compute_burnout_risk([p.label for p in predictions])
