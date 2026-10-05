from datetime import datetime

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user, get_current_user_ws
from app.core.exceptions import AppError
from app.core.security import jwt as jwt_utils
from app.domain.auth.entities import User
from app.infrastructure.db.emotion_infra import (
    SqlEmotionBaselineRepository,
    SqlEmotionPredictionRepository,
    SqlKeystrokeFeatureRepository,
    SqlSessionRepository,
)
from app.infrastructure.db.repositories.settings_repository import SqlSettingsRepository
from app.infrastructure.db.session import get_db
from app.services.emotion import EmotionService

router = APIRouter(prefix="/emotion", tags=["emotion"])


class PredictionOut(BaseModel):
    id: str
    session_id: str
    label: str
    confidence: float
    model_version: str
    created_at: datetime


class BaselineOut(BaseModel):
    avg_hold_time: float
    typing_speed: float
    avg_interkey_delay: float
    error_rate: float
    sample_count: int
    updated_at: datetime


class KeystrokeBatchIn(BaseModel):
    avg_hold_time: float = Field(ge=0)
    typing_speed: float = Field(ge=0)
    avg_interkey_delay: float = Field(ge=0)
    error_rate: float = Field(ge=0, le=1)
    total_keys: int = Field(ge=0)
    window_start: datetime
    window_end: datetime


def get_service(db: Session = Depends(get_db)) -> EmotionService:
    return EmotionService(SqlSessionRepository(db), SqlKeystrokeFeatureRepository(db),
                           SqlEmotionBaselineRepository(db), SqlEmotionPredictionRepository(db))


def _pred_out(p) -> PredictionOut:
    return PredictionOut(id=str(p.id), session_id=str(p.session_id), label=p.label,
                          confidence=p.confidence, model_version=p.model_version, created_at=p.created_at)


def _baseline_out(b) -> BaselineOut:
    return BaselineOut(avg_hold_time=b.avg_hold_time, typing_speed=b.typing_speed,
                        avg_interkey_delay=b.avg_interkey_delay, error_rate=b.error_rate,
                        sample_count=b.sample_count, updated_at=b.updated_at)


@router.get("/current", response_model=PredictionOut | None)
def get_current(user: User = Depends(get_current_user), svc: EmotionService = Depends(get_service)):
    p = svc.get_current(user.id)
    return _pred_out(p) if p else None


@router.get("/history", response_model=list[PredictionOut])
def get_history(from_: datetime | None = Query(default=None, alias="from"), to: datetime | None = None,
                 limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
                 granularity: str | None = None,  # accepted, no-op — not specified anywhere
                 user: User = Depends(get_current_user), svc: EmotionService = Depends(get_service)):
    return [_pred_out(p) for p in svc.get_history(user.id, from_, to, limit, offset)]


@router.get("/baseline", response_model=BaselineOut | None)
def get_baseline(user: User = Depends(get_current_user), svc: EmotionService = Depends(get_service)):
    b = svc.get_baseline(user.id)
    return _baseline_out(b) if b else None


@router.post("/baseline/recalibrate", response_model=BaselineOut)
def recalibrate(user: User = Depends(get_current_user), svc: EmotionService = Depends(get_service)):
    return _baseline_out(svc.recalibrate(user.id))


@router.websocket("/stream")
async def stream(websocket: WebSocket, db: Session = Depends(get_db)):
    try:
        user = await get_current_user_ws(websocket, db)
    except (jwt_utils.InvalidTokenError, jwt_utils.TokenExpiredError):
        await websocket.close(code=4401)
        return

    settings_row = SqlSettingsRepository(db).get_by_user_id(user.id)
    consent = settings_row.privacy.keystroke_analysis if settings_row else True  # default per Module 2
    if not consent:
        await websocket.close(code=4403)
        return

    await websocket.accept()
    svc = get_service(db)
    session = svc.start_session(user.id)
    db.commit()  # WS is one long-lived request; commit per-batch below, not just at the end

    try:
        while True:
            raw = await websocket.receive_json()
            try:
                batch = KeystrokeBatchIn(**raw)
            except Exception:
                await websocket.send_json({"error": "INVALID_BATCH"})
                continue
            try:
                prediction = svc.ingest(session.id, user.id, consent, **batch.model_dump())
                db.commit()
            except AppError as exc:
                db.rollback()
                await websocket.send_json({"error": exc.error_code, "message": str(exc)})
                continue
            await websocket.send_json(_pred_out(prediction).model_dump(mode="json"))
    except WebSocketDisconnect:
        svc.end_session(session.id)
        db.commit()
