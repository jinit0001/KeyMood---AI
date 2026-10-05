from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user
from app.domain.auth.entities import User
from app.infrastructure.db.session import get_db
from app.infrastructure.db.sos_infra import (
    SqlEmergencyContactRepository,
    SqlGuardianConsentRepository,
    SqlGuardianRepository,
    SqlRiskEscalationRepository,
    SqlRiskEventRepository,
    SqlSosNotificationRepository,
)
from app.services.sos import SosService

router = APIRouter(prefix="/sos", tags=["sos"])


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = None
    email: str | None = None
    relationship: str | None = None


class ContactOut(BaseModel):
    id: str
    name: str
    phone: str | None
    email: str | None
    relationship: str | None
    created_at: datetime


class GuardianOut(BaseModel):
    id: str
    guardian_user_id: str | None
    guardian_contact_id: str | None
    created_at: datetime


class GuardianInviteOut(BaseModel):
    guardian: GuardianOut
    consent_token: str  # stands in for real email/SMS delivery


class GuardianInviteIn(ContactIn):
    guardian_user_id: str | None = None


class ConsentIn(BaseModel):
    token: str
    consent_given: bool


class TriggerIn(BaseModel):
    source: str
    context: dict = Field(default_factory=dict)


class TriggerOut(BaseModel):
    risk_event_id: str
    checkin_shown: bool


class NotificationOut(BaseModel):
    id: str
    guardian_id: str
    channel: str
    delivery_status: str
    sent_at: datetime


class AuditEscalationOut(BaseModel):
    action: str
    actor: str
    created_at: datetime


class AuditEntryOut(BaseModel):
    risk_event_id: str
    source: str
    risk_level: str
    created_at: datetime
    escalations: list[AuditEscalationOut]


def get_service(db: Session = Depends(get_db)) -> SosService:
    return SosService(SqlEmergencyContactRepository(db), SqlGuardianRepository(db),
                       SqlGuardianConsentRepository(db), SqlRiskEventRepository(db),
                       SqlRiskEscalationRepository(db), SqlSosNotificationRepository(db))


def _contact_out(c) -> ContactOut:
    return ContactOut(id=str(c.id), name=c.name, phone=c.phone, email=c.email,
                       relationship=c.relationship, created_at=c.created_at)


def _guardian_out(g) -> GuardianOut:
    return GuardianOut(id=str(g.id), guardian_user_id=str(g.guardian_user_id) if g.guardian_user_id else None,
                        guardian_contact_id=str(g.guardian_contact_id) if g.guardian_contact_id else None,
                        created_at=g.created_at)


@router.get("/contacts", response_model=list[ContactOut])
def list_contacts(user: User = Depends(get_current_user), svc: SosService = Depends(get_service)):
    return [_contact_out(c) for c in svc.list_contacts(user.id)]


@router.post("/contacts", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def add_contact(payload: ContactIn, user: User = Depends(get_current_user), svc: SosService = Depends(get_service)):
    return _contact_out(svc.add_contact(user.id, payload.name, payload.phone, payload.email, payload.relationship))


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: UUID, user: User = Depends(get_current_user), svc: SosService = Depends(get_service)):
    svc.delete_contact(user.id, contact_id)


@router.get("/guardians", response_model=list[GuardianOut])
def list_guardians(user: User = Depends(get_current_user), svc: SosService = Depends(get_service)):
    return [_guardian_out(g) for g in svc.list_guardians(user.id)]


@router.post("/guardians", response_model=GuardianInviteOut, status_code=status.HTTP_201_CREATED)
def invite_guardian(payload: GuardianInviteIn, user: User = Depends(get_current_user), svc: SosService = Depends(get_service)):
    g, token = svc.invite_guardian(user.id, payload.name, payload.phone, payload.email, payload.relationship,
                                    UUID(payload.guardian_user_id) if payload.guardian_user_id else None)
    return GuardianInviteOut(guardian=_guardian_out(g), consent_token=token)


@router.delete("/guardians/{guardian_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_guardian(guardian_id: UUID, user: User = Depends(get_current_user), svc: SosService = Depends(get_service)):
    svc.delete_guardian(user.id, guardian_id)


@router.post("/guardians/{guardian_id}/consent", status_code=status.HTTP_204_NO_CONTENT)
def guardian_consent(guardian_id: UUID, payload: ConsentIn, svc: SosService = Depends(get_service)):
    # Deliberately no get_current_user — guardian may not be a platform user.
    svc.confirm_guardian_consent(guardian_id, payload.token, payload.consent_given)


@router.post("/trigger", response_model=TriggerOut)
def trigger(payload: TriggerIn, user: User = Depends(get_current_user), svc: SosService = Depends(get_service)):
    event, checkin_shown = svc.trigger(user.id, payload.source, payload.context)
    return TriggerOut(risk_event_id=str(event.id), checkin_shown=checkin_shown)


@router.post("/escalations/{risk_event_id}/confirm", response_model=list[NotificationOut])
def confirm_escalation(risk_event_id: UUID, user: User = Depends(get_current_user), svc: SosService = Depends(get_service)):
    return [NotificationOut(id=str(n.id), guardian_id=str(n.guardian_id), channel=n.channel,
                             delivery_status=n.delivery_status, sent_at=n.sent_at)
            for n in svc.confirm_escalation(user.id, risk_event_id)]


@router.post("/escalations/{risk_event_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_escalation(risk_event_id: UUID, user: User = Depends(get_current_user), svc: SosService = Depends(get_service)):
    svc.dismiss_escalation(user.id, risk_event_id)


@router.get("/audit", response_model=list[AuditEntryOut])
def audit(user: User = Depends(get_current_user), svc: SosService = Depends(get_service)):
    return [
        AuditEntryOut(risk_event_id=str(e.id), source=e.source, risk_level=e.risk_level, created_at=e.created_at,
                      escalations=[AuditEscalationOut(action=x.action, actor=x.actor, created_at=x.created_at) for x in escs])
        for e, escs in svc.get_audit(user.id)
    ]
