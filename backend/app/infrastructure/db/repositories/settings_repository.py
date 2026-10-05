from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.profile.entities import AIPreferences, NotificationSettings, PrivacySettings, UserSettings
from app.infrastructure.db.models.user_settings import UserSettingsModel


def _to_domain(row: UserSettingsModel) -> UserSettings:
    return UserSettings(
        user_id=row.user_id,
        privacy=PrivacySettings(**row.privacy),
        notifications=NotificationSettings(**row.notifications),
        ai_preferences=AIPreferences(**row.ai_preferences),
        updated_at=row.updated_at,
    )


class SqlSettingsRepository:
    """Implements domain.profile.ports.SettingsRepository."""

    def __init__(self, session: Session):
        self._session = session

    def get_by_user_id(self, user_id: UUID) -> UserSettings | None:
        stmt = select(UserSettingsModel).where(UserSettingsModel.user_id == user_id)
        row = self._session.execute(stmt).scalar_one_or_none()
        return _to_domain(row) if row else None

    def create_default(self, user_id: UUID) -> UserSettings:
        row = UserSettingsModel(
            user_id=user_id,
            privacy=asdict(PrivacySettings()),
            notifications=asdict(NotificationSettings()),
            ai_preferences=asdict(AIPreferences()),
        )
        self._session.add(row)
        self._session.flush()
        return _to_domain(row)

    def update(self, settings: UserSettings) -> None:
        row = self._session.get(UserSettingsModel, settings.user_id)
        if row is None:
            raise ValueError(f"UserSettings {settings.user_id} not found")
        row.privacy = asdict(settings.privacy)
        row.notifications = asdict(settings.notifications)
        row.ai_preferences = asdict(settings.ai_preferences)
        self._session.flush()
