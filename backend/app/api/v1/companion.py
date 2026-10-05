from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user
from app.infrastructure.db.session import get_db
from app.infrastructure.db.companion_infra import SqlChatSessionRepository, SqlChatMessageRepository
from app.infrastructure.db.emotion_infra import (
    SqlEmotionBaselineRepository,
    SqlEmotionPredictionRepository,
    SqlKeystrokeFeatureRepository,
    SqlSessionRepository,
)
from app.infrastructure.db.sos_infra import (
    SqlEmergencyContactRepository,
    SqlGuardianConsentRepository,
    SqlGuardianRepository,
    SqlRiskEscalationRepository,
    SqlRiskEventRepository,
    SqlSosNotificationRepository,
)
from app.services.companion import AICompanionService
from app.services.emotion import EmotionService
from app.services.sos import SosService

# --- Integration adapters -------------------------------------------------
# Thin wrappers that connect the Companion to the existing modules, so it
# never reimplements their logic:
#   Module 3 (Emotion) -> latest detected mood label
#   Module 4 (SOS)     -> the ONLY path that ever creates a risk event


class EmotionMoodAdapter:
    """Reads the user's latest mood label from Module 3 (None if no data yet)."""

    def __init__(self, db: Session) -> None:
        self._svc = EmotionService(
            SqlSessionRepository(db),
            SqlKeystrokeFeatureRepository(db),
            SqlEmotionBaselineRepository(db),
            SqlEmotionPredictionRepository(db),
        )

    def latest_mood(self, user_id: UUID) -> str | None:
        prediction = self._svc.get_current(user_id)
        return prediction.label if prediction else None


class SosRiskAdapter:
    """Creates a risk event through Module 4's SosService.trigger().

    Per Module 4's design this only records the event and shows an in-app
    check-in; a guardian is notified only after the user confirms.
    """

    def __init__(self, db: Session) -> None:
        self._svc = SosService(
            SqlEmergencyContactRepository(db),
            SqlGuardianRepository(db),
            SqlGuardianConsentRepository(db),
            SqlRiskEventRepository(db),
            SqlRiskEscalationRepository(db),
            SqlSosNotificationRepository(db),
        )

    def trigger(self, user_id: UUID, note: str) -> None:
        self._svc.trigger(user_id, "system", {"risk_level": "high", "note": note, "origin": "ai_companion"})


router = APIRouter(prefix="/companion", tags=["companion"])


def _service(db: Session) -> AICompanionService:
    return AICompanionService(
        SqlChatSessionRepository(db),
        SqlChatMessageRepository(db),
        EmotionMoodAdapter(db),
        SosRiskAdapter(db),
    )


class MessageIn(BaseModel):
    content: str


class MessageOut(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    flagged_crisis: bool
    created_at: datetime


@router.post("/message", response_model=MessageOut, status_code=201)
def send_message(body: MessageIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    svc = _service(db)
    reply = svc.send_message(user.id, body.content)
    db.commit()
    return MessageOut(**reply.__dict__)


@router.get("/history", response_model=list[MessageOut])
def history(limit: int = Query(default=50, ge=1, le=200), user=Depends(get_current_user), db: Session = Depends(get_db)):
    svc = _service(db)
    msgs = svc.history(user.id, limit)
    return [MessageOut(**m.__dict__) for m in msgs]
