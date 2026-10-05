import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, and_, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session as DbSession, mapped_column

from app.domain.emotion import EmotionBaseline, EmotionPrediction, KeystrokeFeatureBatch, Session
from app.infrastructure.db.base import Base


class SessionModel(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    device_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class KeystrokeFeatureModel(Base):
    __tablename__ = "keystroke_features"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    avg_hold_time: Mapped[float] = mapped_column(Float, nullable=False)
    typing_speed: Mapped[float] = mapped_column(Float, nullable=False)
    avg_interkey_delay: Mapped[float] = mapped_column(Float, nullable=False)
    error_rate: Mapped[float] = mapped_column(Float, nullable=False)
    total_keys: Mapped[int] = mapped_column(Integer, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EmotionBaselineModel(Base):
    __tablename__ = "emotion_baselines"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    avg_hold_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    typing_speed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_interkey_delay: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class EmotionPredictionModel(Base):
    __tablename__ = "emotion_predictions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SqlSessionRepository:
    def __init__(self, db: DbSession): self._db = db

    def add(self, s: Session) -> None:
        self._db.add(SessionModel(id=s.id, user_id=s.user_id, started_at=s.started_at, device_info=s.device_info))
        self._db.flush()

    def end_session(self, session_id, ended_at) -> None:
        row = self._db.get(SessionModel, session_id)
        if row:
            row.ended_at = ended_at
            self._db.flush()


class SqlKeystrokeFeatureRepository:
    def __init__(self, db: DbSession): self._db = db

    def add(self, b: KeystrokeFeatureBatch) -> None:
        self._db.add(KeystrokeFeatureModel(id=b.id, session_id=b.session_id, avg_hold_time=b.avg_hold_time,
                                            typing_speed=b.typing_speed, avg_interkey_delay=b.avg_interkey_delay,
                                            error_rate=b.error_rate, total_keys=b.total_keys,
                                            window_start=b.window_start, window_end=b.window_end))
        self._db.flush()


class SqlEmotionBaselineRepository:
    def __init__(self, db: DbSession): self._db = db

    def get_by_user_id(self, user_id) -> EmotionBaseline | None:
        row = self._db.get(EmotionBaselineModel, user_id)
        return None if row is None else EmotionBaseline(
            user_id=row.user_id, avg_hold_time=row.avg_hold_time, typing_speed=row.typing_speed,
            avg_interkey_delay=row.avg_interkey_delay, error_rate=row.error_rate,
            sample_count=row.sample_count, updated_at=row.updated_at)

    def upsert(self, baseline: EmotionBaseline) -> None:
        row = self._db.get(EmotionBaselineModel, baseline.user_id)
        if row is None:
            row = EmotionBaselineModel(user_id=baseline.user_id)
            self._db.add(row)
        row.avg_hold_time, row.typing_speed = baseline.avg_hold_time, baseline.typing_speed
        row.avg_interkey_delay, row.error_rate = baseline.avg_interkey_delay, baseline.error_rate
        row.sample_count = baseline.sample_count
        self._db.flush()


class SqlEmotionPredictionRepository:
    def __init__(self, db: DbSession): self._db = db

    def add(self, p: EmotionPrediction) -> None:
        self._db.add(EmotionPredictionModel(id=p.id, session_id=p.session_id, user_id=p.user_id, label=p.label,
                                             confidence=p.confidence, model_version=p.model_version))
        self._db.flush()

    def get_latest_for_user(self, user_id) -> EmotionPrediction | None:
        stmt = select(EmotionPredictionModel).where(EmotionPredictionModel.user_id == user_id).order_by(
            EmotionPredictionModel.created_at.desc()).limit(1)
        row = self._db.execute(stmt).scalar_one_or_none()
        return self._to_domain(row) if row else None

    def get_history(self, user_id, from_dt, to_dt, limit, offset) -> list[EmotionPrediction]:
        conditions = [EmotionPredictionModel.user_id == user_id]
        if from_dt: conditions.append(EmotionPredictionModel.created_at >= from_dt)
        if to_dt: conditions.append(EmotionPredictionModel.created_at <= to_dt)
        stmt = select(EmotionPredictionModel).where(and_(*conditions)).order_by(
            EmotionPredictionModel.created_at.desc()).limit(limit).offset(offset)
        return [self._to_domain(r) for r in self._db.execute(stmt).scalars().all()]

    def _to_domain(self, row) -> EmotionPrediction:
        return EmotionPrediction(id=row.id, session_id=row.session_id, user_id=row.user_id, label=row.label,
                                  confidence=row.confidence, model_version=row.model_version, created_at=row.created_at)
