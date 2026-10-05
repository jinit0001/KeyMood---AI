"""
Repository interfaces (ports) for the Profile & Settings bounded context.
Concrete implementations live in infrastructure/db/repositories/.
Services depend only on these Protocols — see tests/fakes.py for the
in-memory implementations used in unit tests.
"""
from typing import Protocol
from uuid import UUID

from app.domain.profile.entities import DataExportRequest, Profile, UserSettings


class ProfileRepository(Protocol):
    def get_by_user_id(self, user_id: UUID) -> Profile | None: ...
    def update(self, profile: Profile) -> None: ...


class SettingsRepository(Protocol):
    def get_by_user_id(self, user_id: UUID) -> UserSettings | None: ...
    def create_default(self, user_id: UUID) -> UserSettings: ...
    def update(self, settings: UserSettings) -> None: ...


class DataExportRepository(Protocol):
    def add(self, request: DataExportRequest) -> None: ...
