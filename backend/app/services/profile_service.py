"""
ProfileService — orchestrates Profile use cases. Depends only on domain
Protocols, never SQLAlchemy/FastAPI directly (LLD.md §5/§6), same
pattern as AuthService.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from app.core.exceptions import ProfileNotFoundError, ValidationError
from app.domain.profile.entities import Profile
from app.domain.profile.ports import ProfileRepository

logger = logging.getLogger("keymood.profile")

MAX_DISPLAY_NAME_LENGTH = 80
MAX_BIO_LENGTH = 300


def validate_profile_fields(display_name: str | None, bio: str | None) -> list[str]:
    """Matches API_SPEC.md §2's 'validated lengths per DATABASE.md' —
    DATABASE.md: display_name VARCHAR(80), bio VARCHAR(300)."""
    errors: list[str] = []
    if display_name is not None:
        stripped = display_name.strip()
        if not (1 <= len(stripped) <= MAX_DISPLAY_NAME_LENGTH):
            errors.append(f"display_name must be 1-{MAX_DISPLAY_NAME_LENGTH} characters.")
    if bio is not None and len(bio) > MAX_BIO_LENGTH:
        errors.append(f"bio must be at most {MAX_BIO_LENGTH} characters.")
    return errors


class ProfileService:
    def __init__(self, profile_repo: ProfileRepository):
        self._profiles = profile_repo

    def get_profile(self, user_id: UUID) -> Profile:
        profile = self._profiles.get_by_user_id(user_id)
        if profile is None:
            # Shouldn't happen in practice — Auth creates this row at
            # registration — but the API contract needs a real error path
            # for it rather than an unhandled 500 if it ever does.
            raise ProfileNotFoundError()
        return profile

    def update_profile(
        self,
        user_id: UUID,
        display_name: str | None = None,
        avatar_url: str | None = None,
        bio: str | None = None,
        timezone_name: str | None = None,
    ) -> Profile:
        errors = validate_profile_fields(display_name, bio)
        if errors:
            raise ValidationError("Profile update failed validation.", {"errors": errors})

        profile = self.get_profile(user_id)
        if display_name is not None:
            profile.display_name = display_name.strip()
        if avatar_url is not None:
            profile.avatar_url = avatar_url
        if bio is not None:
            profile.bio = bio
        if timezone_name is not None:
            profile.timezone = timezone_name
        profile.updated_at = datetime.now(timezone.utc)

        self._profiles.update(profile)
        logger.info("profile_updated", extra={"user_id": str(user_id)})
        return profile
