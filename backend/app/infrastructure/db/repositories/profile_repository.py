from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.profile.entities import Profile
from app.infrastructure.db.models.user_profile import UserProfileModel


def _to_domain(row: UserProfileModel) -> Profile:
    return Profile(
        user_id=row.user_id,
        display_name=row.display_name,
        avatar_url=row.avatar_url,
        bio=row.bio,
        timezone=row.timezone,
        updated_at=row.updated_at,
    )


class SqlProfileRepository:
    """Implements domain.profile.ports.ProfileRepository. Full read/update
    over the same user_profiles table Auth's SqlProfileInitializer only
    INSERTs the initial row into."""

    def __init__(self, session: Session):
        self._session = session

    def get_by_user_id(self, user_id: UUID) -> Profile | None:
        stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
        row = self._session.execute(stmt).scalar_one_or_none()
        return _to_domain(row) if row else None

    def update(self, profile: Profile) -> None:
        row = self._session.get(UserProfileModel, profile.user_id)
        if row is None:
            raise ValueError(f"UserProfile {profile.user_id} not found")
        row.display_name = profile.display_name
        row.avatar_url = profile.avatar_url
        row.bio = profile.bio
        row.timezone = profile.timezone
        self._session.flush()
