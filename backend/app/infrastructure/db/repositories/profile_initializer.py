from uuid import UUID

from sqlalchemy.orm import Session

from app.infrastructure.db.models.user_profile import UserProfileModel


class SqlProfileInitializer:
    """Implements domain.auth.repositories.ProfileInitializer."""

    def __init__(self, session: Session):
        self._session = session

    def create_initial_profile(self, user_id: UUID, display_name: str) -> None:
        row = UserProfileModel(user_id=user_id, display_name=display_name, timezone="UTC")
        self._session.add(row)
        self._session.flush()
