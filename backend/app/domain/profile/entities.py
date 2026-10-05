"""
Domain entities for the Profile & Settings bounded context.

Per LLD.md's layering: pure dataclasses, no SQLAlchemy/Pydantic here.
`user_profiles` matches DATABASE.md exactly (it's created by Auth at
registration; this module owns full read/update).

`user_settings` / `data_export_requests` are NOT in DATABASE.md — the
Settings section of API_SPEC.md (§11) describes the endpoints but the
underlying schema for privacy/notification/AI-preference storage was
never specified. This is a gap-fill, flagged the same way Module 1
flagged its own gaps (see MODULE_2_STATUS.md), not a silent invention.
"""
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class Profile:
    user_id: UUID
    display_name: str
    avatar_url: str | None
    bio: str | None
    timezone: str
    updated_at: datetime


@dataclass
class PrivacySettings:
    """Granular toggles per data category. Categories chosen to match
    what Auth + the planned modules actually collect (SECURITY.md's data
    categories: keystroke/emotion data, journal, companion memory,
    guardian/SOS sharing, analytics). Not an enumerated requirement
    anywhere — gap-filled, matching what's collected elsewhere in the
    architecture docs."""

    keystroke_analysis: bool = True
    journal_analysis: bool = True
    companion_memory: bool = True
    guardian_sharing: bool = True
    analytics_sharing: bool = True


@dataclass
class NotificationSettings:
    """Per-category on/off, per API_SPEC.md §11. Categories chosen to
    match planned modules (Messaging, Social, AI Companion, Goals, SOS)."""

    messages: bool = True
    friend_requests: bool = True
    companion_nudges: bool = True
    goal_reminders: bool = True
    # Safety-critical — the UI should discourage disabling this, but the
    # API doesn't block it; that's a product/UX decision, not this
    # module's to enforce silently.
    sos_alerts: bool = True


@dataclass
class AIPreferences:
    """Companion tone, coaching frequency, feature opt-outs, per
    API_SPEC.md §11. Enum values are not specified anywhere — gap-filled
    with a small, defensible set; documented as such."""

    companion_tone: str = "supportive"  # supportive | direct | playful
    coaching_frequency: str = "normal"  # low | normal | high
    feature_opt_outs: list[str] = field(default_factory=list)


@dataclass
class UserSettings:
    user_id: UUID
    privacy: PrivacySettings
    notifications: NotificationSettings
    ai_preferences: AIPreferences
    updated_at: datetime


@dataclass
class DataExportRequest:
    id: UUID
    user_id: UUID
    status: str  # pending | completed | failed
    download_url: str | None
    expires_at: datetime | None
    requested_at: datetime
    completed_at: datetime | None
