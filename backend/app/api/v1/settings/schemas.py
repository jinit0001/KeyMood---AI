from datetime import datetime

from pydantic import BaseModel, Field


class PrivacySettingsResponse(BaseModel):
    keystroke_analysis: bool
    journal_analysis: bool
    companion_memory: bool
    guardian_sharing: bool
    analytics_sharing: bool


class PrivacySettingsUpdateRequest(BaseModel):
    keystroke_analysis: bool | None = None
    journal_analysis: bool | None = None
    companion_memory: bool | None = None
    guardian_sharing: bool | None = None
    analytics_sharing: bool | None = None


class NotificationSettingsResponse(BaseModel):
    messages: bool
    friend_requests: bool
    companion_nudges: bool
    goal_reminders: bool
    sos_alerts: bool


class NotificationSettingsUpdateRequest(BaseModel):
    messages: bool | None = None
    friend_requests: bool | None = None
    companion_nudges: bool | None = None
    goal_reminders: bool | None = None
    sos_alerts: bool | None = None


class AIPreferencesResponse(BaseModel):
    companion_tone: str
    coaching_frequency: str
    feature_opt_outs: list[str]


class AIPreferencesUpdateRequest(BaseModel):
    companion_tone: str | None = None
    coaching_frequency: str | None = None
    feature_opt_outs: list[str] | None = None


class ExportResponse(BaseModel):
    request_id: str
    status: str
    requested_at: datetime


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
