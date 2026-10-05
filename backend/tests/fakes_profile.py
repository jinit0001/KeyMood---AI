"""
In-memory fakes for the Profile & Settings bounded context. Same pattern
as tests/fakes.py — implement the exact same Protocols as the SQL
repositories so ProfileService/SettingsService can be unit tested with
no database.
"""
from uuid import UUID

from app.domain.profile.entities import (
    AIPreferences,
    DataExportRequest,
    NotificationSettings,
    PrivacySettings,
    Profile,
    UserSettings,
)


class FakeProfileRepository:
    def __init__(self):
        self._by_user_id: dict[UUID, Profile] = {}

    def seed(self, profile: Profile) -> None:
        self._by_user_id[profile.user_id] = profile

    def get_by_user_id(self, user_id: UUID) -> Profile | None:
        return self._by_user_id.get(user_id)

    def update(self, profile: Profile) -> None:
        self._by_user_id[profile.user_id] = profile


class FakeSettingsRepository:
    def __init__(self):
        self._by_user_id: dict[UUID, UserSettings] = {}

    def get_by_user_id(self, user_id: UUID) -> UserSettings | None:
        return self._by_user_id.get(user_id)

    def create_default(self, user_id: UUID) -> UserSettings:
        from datetime import datetime, timezone

        settings = UserSettings(
            user_id=user_id,
            privacy=PrivacySettings(),
            notifications=NotificationSettings(),
            ai_preferences=AIPreferences(),
            updated_at=datetime.now(timezone.utc),
        )
        self._by_user_id[user_id] = settings
        return settings

    def update(self, settings: UserSettings) -> None:
        self._by_user_id[settings.user_id] = settings


class FakeDataExportRepository:
    def __init__(self):
        self.requests: list[DataExportRequest] = []

    def add(self, request: DataExportRequest) -> None:
        self.requests.append(request)
