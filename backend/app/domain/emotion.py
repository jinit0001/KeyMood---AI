from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass
class Session:
    id: UUID
    user_id: UUID
    started_at: datetime
    ended_at: datetime | None
    device_info: dict | None


@dataclass
class KeystrokeFeatureBatch:
    id: UUID
    session_id: UUID
    avg_hold_time: float
    typing_speed: float
    avg_interkey_delay: float
    error_rate: float
    total_keys: int
    window_start: datetime
    window_end: datetime


@dataclass
class EmotionBaseline:
    user_id: UUID
    avg_hold_time: float
    typing_speed: float
    avg_interkey_delay: float
    error_rate: float
    sample_count: int
    updated_at: datetime


@dataclass
class EmotionPrediction:
    id: UUID
    session_id: UUID
    user_id: UUID
    label: str
    confidence: float
    model_version: str
    created_at: datetime


class SessionRepository(Protocol):
    def add(self, session: Session) -> None: ...
    def end_session(self, session_id: UUID, ended_at: datetime) -> None: ...


class KeystrokeFeatureRepository(Protocol):
    def add(self, batch: KeystrokeFeatureBatch) -> None: ...


class EmotionBaselineRepository(Protocol):
    def get_by_user_id(self, user_id: UUID) -> EmotionBaseline | None: ...
    def upsert(self, baseline: EmotionBaseline) -> None: ...


class EmotionPredictionRepository(Protocol):
    def add(self, prediction: EmotionPrediction) -> None: ...
    def get_latest_for_user(self, user_id: UUID) -> EmotionPrediction | None: ...
    def get_history(
        self, user_id: UUID, from_dt: datetime | None, to_dt: datetime | None, limit: int, offset: int
    ) -> list[EmotionPrediction]: ...
