"""
Rule-based (NOT trained ML) classifier: deviation from the user's own
running-average baseline, not fixed thresholds. A real trained model
is future work; classify() is isolated so it can be swapped later.
"""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.exceptions import ConsentRequiredError, ValidationError
from app.domain.emotion import (
    EmotionBaseline,
    EmotionBaselineRepository,
    EmotionPrediction,
    EmotionPredictionRepository,
    KeystrokeFeatureBatch,
    KeystrokeFeatureRepository,
    Session,
    SessionRepository,
)

MODEL_VERSION = "rule-based-v1"
COLD_START = {"avg_hold_time": 100.0, "typing_speed": 45.0, "avg_interkey_delay": 180.0, "error_rate": 0.05}
MIN_SAMPLES_FOR_CONFIDENCE = 8


def classify(batch: KeystrokeFeatureBatch, baseline: EmotionBaseline | None) -> tuple[str, float]:
    ref = COLD_START if baseline is None else {
        "avg_hold_time": baseline.avg_hold_time, "typing_speed": baseline.typing_speed,
        "avg_interkey_delay": baseline.avg_interkey_delay, "error_rate": baseline.error_rate,
    }
    sample_count = 0 if baseline is None else baseline.sample_count

    def ratio(a, b):
        return 0.0 if abs(b) < 1e-9 else a / b

    speed_dev = ratio(batch.typing_speed - ref["typing_speed"], ref["typing_speed"])
    delay_dev = ratio(batch.avg_interkey_delay - ref["avg_interkey_delay"], ref["avg_interkey_delay"])
    error_dev = batch.error_rate - ref["error_rate"]

    if batch.error_rate > 0.15 or error_dev > 0.08:
        label, strength = "stressed", max(abs(error_dev) * 6, batch.error_rate)
    elif speed_dev < -0.25 or delay_dev > 0.3:
        label, strength = "tired", max(abs(speed_dev), abs(delay_dev))
    elif speed_dev > 0.2 and error_dev <= 0.02:
        label, strength = "happy", speed_dev
    elif speed_dev > 0.1 and abs(delay_dev) < 0.15:
        label, strength = "focused", speed_dev
    else:
        label, strength = "calm", 1 - min(abs(speed_dev) + abs(delay_dev) + abs(error_dev), 1)

    baseline_conf = min(1.0, sample_count / MIN_SAMPLES_FOR_CONFIDENCE)
    signal_conf = min(1.0, max(0.15, strength))
    confidence = max(50.0, min(97.0, round(50 + 47 * baseline_conf * signal_conf, 1)))
    return label, confidence


def update_baseline(batch: KeystrokeFeatureBatch, baseline: EmotionBaseline | None) -> dict:
    if baseline is None or baseline.sample_count == 0:
        return {"avg_hold_time": batch.avg_hold_time, "typing_speed": batch.typing_speed,
                "avg_interkey_delay": batch.avg_interkey_delay, "error_rate": batch.error_rate, "sample_count": 1}
    n = baseline.sample_count
    return {
        "avg_hold_time": baseline.avg_hold_time + (batch.avg_hold_time - baseline.avg_hold_time) / (n + 1),
        "typing_speed": baseline.typing_speed + (batch.typing_speed - baseline.typing_speed) / (n + 1),
        "avg_interkey_delay": baseline.avg_interkey_delay + (batch.avg_interkey_delay - baseline.avg_interkey_delay) / (n + 1),
        "error_rate": baseline.error_rate + (batch.error_rate - baseline.error_rate) / (n + 1),
        "sample_count": n + 1,
    }


class EmotionService:
    def __init__(self, sessions: SessionRepository, keystroke: KeystrokeFeatureRepository,
                 baselines: EmotionBaselineRepository, predictions: EmotionPredictionRepository):
        self._sessions, self._keystroke = sessions, keystroke
        self._baselines, self._predictions = baselines, predictions

    def start_session(self, user_id: UUID, device_info: dict | None = None) -> Session:
        session = Session(id=uuid4(), user_id=user_id, started_at=datetime.now(timezone.utc),
                           ended_at=None, device_info=device_info)
        self._sessions.add(session)
        return session

    def end_session(self, session_id: UUID) -> None:
        self._sessions.end_session(session_id, datetime.now(timezone.utc))

    def ingest(self, session_id: UUID, user_id: UUID, consent_granted: bool, **fields) -> EmotionPrediction:
        if not consent_granted:
            raise ConsentRequiredError()
        if fields["total_keys"] < 0 or not (0.0 <= fields["error_rate"] <= 1.0):
            raise ValidationError("Invalid keystroke feature batch.")

        batch = KeystrokeFeatureBatch(id=uuid4(), session_id=session_id, **fields)
        self._keystroke.add(batch)

        baseline = self._baselines.get_by_user_id(user_id)
        label, confidence = classify(batch, baseline)
        updated = update_baseline(batch, baseline)
        self._baselines.upsert(EmotionBaseline(user_id=user_id, updated_at=datetime.now(timezone.utc), **updated))

        prediction = EmotionPrediction(id=uuid4(), session_id=session_id, user_id=user_id, label=label,
                                        confidence=confidence, model_version=MODEL_VERSION,
                                        created_at=datetime.now(timezone.utc))
        self._predictions.add(prediction)
        return prediction

    def get_current(self, user_id: UUID) -> EmotionPrediction | None:
        return self._predictions.get_latest_for_user(user_id)

    def get_history(self, user_id: UUID, from_dt=None, to_dt=None, limit=50, offset=0) -> list[EmotionPrediction]:
        return self._predictions.get_history(user_id, from_dt, to_dt, min(max(limit, 1), 200), offset)

    def get_baseline(self, user_id: UUID) -> EmotionBaseline | None:
        return self._baselines.get_by_user_id(user_id)

    def recalibrate(self, user_id: UUID) -> EmotionBaseline:
        fresh = EmotionBaseline(user_id=user_id, avg_hold_time=0.0, typing_speed=0.0, avg_interkey_delay=0.0,
                                 error_rate=0.0, sample_count=0, updated_at=datetime.now(timezone.utc))
        self._baselines.upsert(fresh)
        return fresh
