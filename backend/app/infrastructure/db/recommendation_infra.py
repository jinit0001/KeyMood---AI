import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session as DbSession, mapped_column

from app.infrastructure.db.base import Base
from app.services.recommendation import Recommendation, RecommendationFeedback


class RecommendationModel(Base):
    __tablename__ = "recommendations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    shown_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RecommendationFeedbackModel(Base):
    __tablename__ = "recommendation_feedback"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("recommendations.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reaction: Mapped[str] = mapped_column(String(15), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SqlRecommendationRepository:
    def __init__(self, db: DbSession): self._db = db

    def add(self, r: Recommendation) -> None:
        self._db.add(RecommendationModel(id=r.id, user_id=r.user_id, type=r.type, payload=r.payload, shown_at=r.shown_at))
        self._db.flush()

    def get_by_id(self, rid) -> Recommendation | None:
        row = self._db.get(RecommendationModel, rid)
        return None if row is None else Recommendation(id=row.id, user_id=row.user_id, type=row.type,
                                                         payload=row.payload, created_at=row.created_at, shown_at=row.shown_at)

    def list_active_for_user(self, user_id, shown_after) -> list[Recommendation]:
        stmt = select(RecommendationModel).where(RecommendationModel.user_id == user_id,
                                                  RecommendationModel.shown_at >= shown_after).order_by(RecommendationModel.created_at.desc())
        return [self.get_by_id(r.id) for r in self._db.execute(stmt).scalars().all()]

    def list_with_feedback(self, user_id, ids) -> set:
        if not ids:
            return set()
        stmt = select(RecommendationFeedbackModel.recommendation_id).where(
            RecommendationFeedbackModel.user_id == user_id, RecommendationFeedbackModel.recommendation_id.in_(ids))
        return set(self._db.execute(stmt).scalars().all())


class SqlRecommendationFeedbackRepository:
    def __init__(self, db: DbSession): self._db = db

    def add(self, f: RecommendationFeedback) -> None:
        self._db.add(RecommendationFeedbackModel(id=f.id, recommendation_id=f.recommendation_id,
                                                  user_id=f.user_id, reaction=f.reaction))
        self._db.flush()
