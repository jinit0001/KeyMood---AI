import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID, insert as pg_insert
from sqlalchemy.orm import Mapped, Session as DbSession, mapped_column

from app.infrastructure.db.base import Base
from app.services.analytics import AnalyticsSnapshot, WellnessScore


class AnalyticsSnapshotModel(Base):
    __tablename__ = "analytics_snapshots"
    __table_args__ = (UniqueConstraint("user_id", "period", "period_start", name="uq_analytics_snapshot"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WellnessScoreModel(Base):
    __tablename__ = "wellness_scores"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    contributing_factors: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SqlAnalyticsSnapshotRepository:
    def __init__(self, db: DbSession): self._db = db

    def get(self, user_id, period, period_start) -> AnalyticsSnapshot | None:
        stmt = select(AnalyticsSnapshotModel).where(AnalyticsSnapshotModel.user_id == user_id,
                                                     AnalyticsSnapshotModel.period == period,
                                                     AnalyticsSnapshotModel.period_start == period_start)
        row = self._db.execute(stmt).scalar_one_or_none()
        return None if row is None else AnalyticsSnapshot(id=row.id, user_id=row.user_id, period=row.period,
                                                            period_start=row.period_start, metrics=row.metrics, created_at=row.created_at)

    def upsert(self, s: AnalyticsSnapshot) -> None:
        stmt = pg_insert(AnalyticsSnapshotModel).values(id=s.id, user_id=s.user_id, period=s.period,
                                                         period_start=s.period_start, metrics=s.metrics)
        stmt = stmt.on_conflict_do_update(constraint="uq_analytics_snapshot", set_={"metrics": stmt.excluded.metrics})
        self._db.execute(stmt)
        self._db.flush()


class SqlWellnessScoreRepository:
    def __init__(self, db: DbSession): self._db = db

    def add(self, s: WellnessScore) -> None:
        self._db.add(WellnessScoreModel(id=s.id, user_id=s.user_id, score=s.score, contributing_factors=s.contributing_factors))
        self._db.flush()

    def get_previous(self, user_id, before) -> WellnessScore | None:
        stmt = select(WellnessScoreModel).where(WellnessScoreModel.user_id == user_id,
                                                 WellnessScoreModel.computed_at < before).order_by(WellnessScoreModel.computed_at.desc()).limit(1)
        row = self._db.execute(stmt).scalar_one_or_none()
        return None if row is None else WellnessScore(id=row.id, user_id=row.user_id, score=row.score,
                                                        contributing_factors=row.contributing_factors, computed_at=row.computed_at)
