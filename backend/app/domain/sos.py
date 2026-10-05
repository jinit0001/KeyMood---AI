from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass
class EmergencyContact:
    id: UUID
    user_id: UUID
    name: str
    phone: str | None
    email: str | None
    relationship: str | None
    created_at: datetime


@dataclass
class Guardian:
    id: UUID
    user_id: UUID
    guardian_user_id: UUID | None
    guardian_contact_id: UUID | None
    created_at: datetime


@dataclass
class GuardianConsent:
    id: UUID
    guardian_id: UUID
    consent_given: bool
    consented_at: datetime | None
    revoked_at: datetime | None


@dataclass
class RiskEvent:
    id: UUID
    user_id: UUID
    source: str
    risk_level: str
    created_at: datetime
    triggers: dict = field(default_factory=dict)


@dataclass
class RiskEscalation:
    id: UUID
    risk_event_id: UUID
    action: str
    actor: str
    created_at: datetime


@dataclass
class SosNotification:
    id: UUID
    escalation_id: UUID
    guardian_id: UUID
    channel: str
    delivery_status: str
    sent_at: datetime


class EmergencyContactRepository(Protocol):
    def add(self, c: EmergencyContact) -> None: ...
    def get_by_id(self, contact_id: UUID) -> EmergencyContact | None: ...
    def list_for_user(self, user_id: UUID) -> list[EmergencyContact]: ...
    def delete(self, contact_id: UUID) -> None: ...


class GuardianRepository(Protocol):
    def add(self, g: Guardian) -> None: ...
    def get_by_id(self, guardian_id: UUID) -> Guardian | None: ...
    def list_for_user(self, user_id: UUID) -> list[Guardian]: ...
    def delete(self, guardian_id: UUID) -> None: ...


class GuardianConsentRepository(Protocol):
    def add(self, c: GuardianConsent) -> None: ...
    def get_by_guardian_id(self, guardian_id: UUID) -> GuardianConsent | None: ...
    def update_consent(self, guardian_id: UUID, consent_given: bool, when: datetime) -> None: ...


class RiskEventRepository(Protocol):
    """Append-only: no update method exists here at all."""
    def add(self, e: RiskEvent) -> None: ...
    def get_by_id(self, event_id: UUID) -> RiskEvent | None: ...
    def list_for_user(self, user_id: UUID) -> list[RiskEvent]: ...


class RiskEscalationRepository(Protocol):
    """Append-only: no update method exists here at all."""
    def add(self, e: RiskEscalation) -> None: ...
    def list_for_event(self, risk_event_id: UUID) -> list[RiskEscalation]: ...


class SosNotificationRepository(Protocol):
    def add(self, n: SosNotification) -> None: ...
