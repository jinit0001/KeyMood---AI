from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user
from app.domain.auth.entities import User
from app.infrastructure.db.analytics_infra import SqlAnalyticsSnapshotRepository, SqlWellnessScoreRepository
from app.infrastructure.db.emotion_infra import SqlEmotionPredictionRepository
from app.infrastructure.db.recommendation_infra import SqlRecommendationFeedbackRepository, SqlRecommendationRepository
from app.infrastructure.db.session import get_db
from app.services.analytics import AnalyticsService
from app.services.recommendation import RecommendationService

recommendations_router = APIRouter(prefix="/recommendations", tags=["recommendations"])
analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])


# --- Recommendations ---
class RecommendationOut(BaseModel):
    id: str
    type: str
    payload: dict
    shown_at: datetime | None
    created_at: datetime


class FeedbackIn(BaseModel):
    reaction: str  # accepted | dismissed | snoozed


class FeedbackOut(BaseModel):
    id: str
    recommendation_id: str
    reaction: str
    created_at: datetime


def get_recommendation_service(db: Session = Depends(get_db)) -> RecommendationService:
    return RecommendationService(SqlRecommendationRepository(db), SqlRecommendationFeedbackRepository(db),
                                  SqlEmotionPredictionRepository(db))


@recommendations_router.get("/current", response_model=list[RecommendationOut])
def current(user: User = Depends(get_current_user), svc: RecommendationService = Depends(get_recommendation_service)):
    return [RecommendationOut(id=str(r.id), type=r.type, payload=r.payload, shown_at=r.shown_at, created_at=r.created_at)
            for r in svc.get_current(user.id)]


@recommendations_router.post("/{recommendation_id}/feedback", response_model=FeedbackOut)
def feedback(recommendation_id: UUID, payload: FeedbackIn, user: User = Depends(get_current_user),
              svc: RecommendationService = Depends(get_recommendation_service)):
    f = svc.submit_feedback(user.id, recommendation_id, payload.reaction)
    return FeedbackOut(id=str(f.id), recommendation_id=str(f.recommendation_id), reaction=f.reaction, created_at=f.created_at)


# --- Analytics ---
class SnapshotOut(BaseModel):
    period: str
    period_start: date
    metrics: dict
    created_at: datetime


class WellnessOut(BaseModel):
    score: float
    trend: str
    delta: float | None
    contributing_factors: dict
    computed_at: datetime


class BurnoutOut(BaseModel):
    level: str
    contributing_factors: dict


def get_analytics_service(db: Session = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(SqlAnalyticsSnapshotRepository(db), SqlWellnessScoreRepository(db),
                             SqlEmotionPredictionRepository(db))


def _snapshot_route(period: str):
    def handler(user: User = Depends(get_current_user), svc: AnalyticsService = Depends(get_analytics_service)) -> SnapshotOut:
        s = svc.get_period_snapshot(user.id, period)
        return SnapshotOut(period=s.period, period_start=s.period_start, metrics=s.metrics, created_at=s.created_at)
    return handler


for _period in ("daily", "weekly", "monthly"):
    analytics_router.get(f"/{_period}", response_model=SnapshotOut)(_snapshot_route(_period))


@analytics_router.get("/wellness-score", response_model=WellnessOut)
def wellness_score(user: User = Depends(get_current_user), svc: AnalyticsService = Depends(get_analytics_service)):
    score, trend, delta = svc.get_wellness_score(user.id)
    return WellnessOut(score=score.score, trend=trend, delta=delta,
                        contributing_factors=score.contributing_factors, computed_at=score.computed_at)


@analytics_router.get("/burnout-risk", response_model=BurnoutOut)
def burnout_risk(user: User = Depends(get_current_user), svc: AnalyticsService = Depends(get_analytics_service)):
    level, factors = svc.get_burnout_risk(user.id)
    return BurnoutOut(level=level, contributing_factors=factors)
