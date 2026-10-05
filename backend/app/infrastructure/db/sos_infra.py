import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session as DbSession, mapped_column

from app.domain.sos import EmergencyContact, Guardian, GuardianConsent, RiskEscalation, RiskEvent, SosNotification
from app.infrastructure.db.base import Base


class EmergencyContactModel(Base):
    __tablename__ = "emergency_contacts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    relationship_label: Mapped[str | None] = mapped_column("relationship", String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GuardianModel(Base):
    __tablename__ = "guardians"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    guardian_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    guardian_contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("emergency_contacts.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GuardianConsentModel(Base):
    __tablename__ = "guardian_consents"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    guardian_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("guardians.id"), nullable=False)
    consent_given: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RiskEventModel(Base):
    __tablename__ = "risk_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(15), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RiskEscalationModel(Base):
    __tablename__ = "risk_escalations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    risk_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("risk_events.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    actor: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SosNotificationModel(Base):
    __tablename__ = "sos_notifications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    escalation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("risk_escalations.id"), nullable=False)
    guardian_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("guardians.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(15), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SqlEmergencyContactRepository:
    def __init__(self, db: DbSession): self._db = db

    def add(self, c: EmergencyContact) -> None:
        self._db.add(EmergencyContactModel(id=c.id, user_id=c.user_id, name=c.name, phone=c.phone,
                                            email=c.email, relationship_label=c.relationship))
        self._db.flush()

    def get_by_id(self, contact_id) -> EmergencyContact | None:
        r = self._db.get(EmergencyContactModel, contact_id)
        return None if r is None else EmergencyContact(id=r.id, user_id=r.user_id, name=r.name, phone=r.phone,
                                                         email=r.email, relationship=r.relationship_label, created_at=r.created_at)

    def list_for_user(self, user_id) -> list[EmergencyContact]:
        rows = self._db.execute(select(EmergencyContactModel).where(EmergencyContactModel.user_id == user_id)).scalars().all()
        return [self.get_by_id(r.id) for r in rows]

    def delete(self, contact_id) -> None:
        r = self._db.get(EmergencyContactModel, contact_id)
        if r:
            self._db.delete(r)
            self._db.flush()


class SqlGuardianRepository:
    def __init__(self, db: DbSession): self._db = db

    def add(self, g: Guardian) -> None:
        self._db.add(GuardianModel(id=g.id, user_id=g.user_id, guardian_user_id=g.guardian_user_id,
                                    guardian_contact_id=g.guardian_contact_id))
        self._db.flush()

    def get_by_id(self, guardian_id) -> Guardian | None:
        r = self._db.get(GuardianModel, guardian_id)
        return None if r is None else Guardian(id=r.id, user_id=r.user_id, guardian_user_id=r.guardian_user_id,
                                                guardian_contact_id=r.guardian_contact_id, created_at=r.created_at)

    def list_for_user(self, user_id) -> list[Guardian]:
        rows = self._db.execute(select(GuardianModel).where(GuardianModel.user_id == user_id)).scalars().all()
        return [self.get_by_id(r.id) for r in rows]

    def delete(self, guardian_id) -> None:
        r = self._db.get(GuardianModel, guardian_id)
        if r:
            self._db.delete(r)
            self._db.flush()


class SqlGuardianConsentRepository:
    def __init__(self, db: DbSession): self._db = db

    def add(self, c: GuardianConsent) -> None:
        self._db.add(GuardianConsentModel(id=c.id, guardian_id=c.guardian_id, consent_given=c.consent_given,
                                           consented_at=c.consented_at, revoked_at=c.revoked_at))
        self._db.flush()

    def get_by_guardian_id(self, guardian_id) -> GuardianConsent | None:
        r = self._db.execute(select(GuardianConsentModel).where(GuardianConsentModel.guardian_id == guardian_id)).scalar_one_or_none()
        return None if r is None else GuardianConsent(id=r.id, guardian_id=r.guardian_id, consent_given=r.consent_given,
                                                        consented_at=r.consented_at, revoked_at=r.revoked_at)

    def update_consent(self, guardian_id, consent_given, when) -> None:
        r = self._db.execute(select(GuardianConsentModel).where(GuardianConsentModel.guardian_id == guardian_id)).scalar_one_or_none()
        if r is None:
            return
        r.consent_given = consent_given
        r.consented_at, r.revoked_at = (when, None) if consent_given else (r.consented_at, when)
        self._db.flush()


class SqlRiskEventRepository:
    """Append-only: no update method."""
    def __init__(self, db: DbSession): self._db = db

    def add(self, e: RiskEvent) -> None:
        self._db.add(RiskEventModel(id=e.id, user_id=e.user_id, source=e.source, risk_level=e.risk_level))
        self._db.flush()

    def get_by_id(self, event_id) -> RiskEvent | None:
        r = self._db.get(RiskEventModel, event_id)
        return None if r is None else RiskEvent(id=r.id, user_id=r.user_id, source=r.source,
                                                  risk_level=r.risk_level, created_at=r.created_at)

    def list_for_user(self, user_id) -> list[RiskEvent]:
        stmt = select(RiskEventModel).where(RiskEventModel.user_id == user_id).order_by(RiskEventModel.created_at.desc())
        return [self.get_by_id(r.id) for r in self._db.execute(stmt).scalars().all()]


class SqlRiskEscalationRepository:
    """Append-only: no update method."""
    def __init__(self, db: DbSession): self._db = db

    def add(self, e: RiskEscalation) -> None:
        self._db.add(RiskEscalationModel(id=e.id, risk_event_id=e.risk_event_id, action=e.action, actor=e.actor))
        self._db.flush()

    def list_for_event(self, risk_event_id) -> list[RiskEscalation]:
        stmt = select(RiskEscalationModel).where(RiskEscalationModel.risk_event_id == risk_event_id).order_by(RiskEscalationModel.created_at.asc())
        return [RiskEscalation(id=r.id, risk_event_id=r.risk_event_id, action=r.action, actor=r.actor, created_at=r.created_at)
                for r in self._db.execute(stmt).scalars().all()]


class SqlSosNotificationRepository:
    def __init__(self, db: DbSession): self._db = db

    def add(self, n: SosNotification) -> None:
        self._db.add(SosNotificationModel(id=n.id, escalation_id=n.escalation_id, guardian_id=n.guardian_id,
                                           channel=n.channel, delivery_status=n.delivery_status))
        self._db.flush()
