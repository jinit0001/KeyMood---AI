from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.exceptions import GuardianNotFoundError, RiskEventNotFoundError, ValidationError
from app.core.security import jwt as jwt_utils
from app.domain.sos import (
    EmergencyContact,
    EmergencyContactRepository,
    Guardian,
    GuardianConsent,
    GuardianConsentRepository,
    GuardianRepository,
    RiskEscalation,
    RiskEscalationRepository,
    RiskEvent,
    RiskEventRepository,
    SosNotification,
    SosNotificationRepository,
)

VALID_SOURCES = {"manual", "system"}
VALID_RISK_LEVELS = {"low", "elevated", "high"}
DEFAULT_RISK_LEVEL = "elevated"


class SosService:
    def __init__(self, contacts: EmergencyContactRepository, guardians: GuardianRepository,
                 consents: GuardianConsentRepository, risk_events: RiskEventRepository,
                 escalations: RiskEscalationRepository, notifications: SosNotificationRepository):
        self._contacts, self._guardians, self._consents = contacts, guardians, consents
        self._risk_events, self._escalations, self._notifications = risk_events, escalations, notifications

    # --- contacts ---
    def add_contact(self, user_id: UUID, name: str, phone: str | None, email: str | None, relationship: str | None) -> EmergencyContact:
        if not name.strip():
            raise ValidationError("Contact name is required.")
        if not phone and not email:
            raise ValidationError("At least one of phone or email is required.")
        c = EmergencyContact(id=uuid4(), user_id=user_id, name=name.strip(), phone=phone, email=email,
                              relationship=relationship, created_at=datetime.now(timezone.utc))
        self._contacts.add(c)
        return c

    def list_contacts(self, user_id: UUID) -> list[EmergencyContact]:
        return self._contacts.list_for_user(user_id)

    def delete_contact(self, user_id: UUID, contact_id: UUID) -> None:
        c = self._contacts.get_by_id(contact_id)
        if c and c.user_id == user_id:
            self._contacts.delete(contact_id)

    # --- guardians ---
    def invite_guardian(self, user_id: UUID, name: str, phone: str | None = None, email: str | None = None,
                         relationship: str | None = None, guardian_user_id: UUID | None = None) -> tuple[Guardian, str]:
        """No real delivery channel exists yet — token is returned directly (see docs)."""
        contact_id = None
        if guardian_user_id is None:
            contact_id = self.add_contact(user_id, name, phone, email, relationship).id
        g = Guardian(id=uuid4(), user_id=user_id, guardian_user_id=guardian_user_id,
                     guardian_contact_id=contact_id, created_at=datetime.now(timezone.utc))
        self._guardians.add(g)
        self._consents.add(GuardianConsent(id=uuid4(), guardian_id=g.id, consent_given=False,
                                            consented_at=None, revoked_at=None))
        return g, jwt_utils.create_guardian_consent_token(str(g.id))

    def list_guardians(self, user_id: UUID) -> list[Guardian]:
        return self._guardians.list_for_user(user_id)

    def delete_guardian(self, user_id: UUID, guardian_id: UUID) -> None:
        g = self._guardians.get_by_id(guardian_id)
        if g and g.user_id == user_id:
            self._guardians.delete(guardian_id)

    def confirm_guardian_consent(self, guardian_id: UUID, token: str, consent_given: bool) -> GuardianConsent:
        """Public/unauthenticated — 'separate auth context' per spec."""
        payload = jwt_utils.decode_token(token, jwt_utils.TokenType.GUARDIAN_CONSENT)
        if payload["sub"] != str(guardian_id):
            raise jwt_utils.InvalidTokenError("Token does not match this guardian.")
        if self._guardians.get_by_id(guardian_id) is None:
            raise GuardianNotFoundError()
        now = datetime.now(timezone.utc)
        self._consents.update_consent(guardian_id, consent_given, now)
        return self._consents.get_by_guardian_id(guardian_id)

    # --- risk events / escalation ---
    def trigger(self, user_id: UUID, source: str, context: dict | None = None) -> tuple[RiskEvent, bool]:
        """Never notifies a guardian directly — only creates a risk_events row + in-app check-in."""
        if source not in VALID_SOURCES:
            raise ValidationError(f"source must be one of {sorted(VALID_SOURCES)}.")
        context = context or {}
        risk_level = context.get("risk_level", DEFAULT_RISK_LEVEL)
        if risk_level not in VALID_RISK_LEVELS:
            raise ValidationError(f"risk_level must be one of {sorted(VALID_RISK_LEVELS)}.")

        event = RiskEvent(id=uuid4(), user_id=user_id, source=source, risk_level=risk_level,
                           created_at=datetime.now(timezone.utc), triggers=context)
        self._risk_events.add(event)
        self._escalations.add(RiskEscalation(id=uuid4(), risk_event_id=event.id, action="checkin_shown",
                                              actor="system", created_at=datetime.now(timezone.utc)))
        return event, True

    def confirm_escalation(self, user_id: UUID, risk_event_id: UUID) -> list[SosNotification]:
        event = self._risk_events.get_by_id(risk_event_id)
        if event is None or event.user_id != user_id:
            raise RiskEventNotFoundError()

        now = datetime.now(timezone.utc)
        self._escalations.add(RiskEscalation(id=uuid4(), risk_event_id=event.id, action="user_confirmed",
                                              actor="user", created_at=now))
        notifications = []
        guardians = self._guardians.list_for_user(user_id)
        if guardians:
            esc = RiskEscalation(id=uuid4(), risk_event_id=event.id, action="guardian_notified",
                                  actor="system", created_at=now)
            self._escalations.add(esc)
            for g in guardians:
                consent = self._consents.get_by_guardian_id(g.id)
                if not consent or not consent.consent_given or consent.revoked_at:
                    continue
                contact = self._contacts.get_by_id(g.guardian_contact_id) if g.guardian_contact_id else None
                channel = "sms" if (contact and contact.phone) else "email" if (contact and contact.email) else "push"
                n = SosNotification(id=uuid4(), escalation_id=esc.id, guardian_id=g.id, channel=channel,
                                     delivery_status="sent", sent_at=now)  # simulated — no real provider wired up
                self._notifications.add(n)
                notifications.append(n)
        return notifications

    def dismiss_escalation(self, user_id: UUID, risk_event_id: UUID) -> None:
        event = self._risk_events.get_by_id(risk_event_id)
        if event is None or event.user_id != user_id:
            raise RiskEventNotFoundError()
        self._escalations.add(RiskEscalation(id=uuid4(), risk_event_id=event.id, action="user_dismissed",
                                              actor="user", created_at=datetime.now(timezone.utc)))

    def get_audit(self, user_id: UUID) -> list[tuple[RiskEvent, list[RiskEscalation]]]:
        events = self._risk_events.list_for_user(user_id)
        return [(e, self._escalations.list_for_event(e.id)) for e in events]
