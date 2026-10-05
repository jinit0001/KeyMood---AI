"""
Profile routes. Path, methods, status codes match API_SPEC.md §2 exactly.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.profile.schemas import ProfileResponse, ProfileUpdateRequest
from app.domain.auth.entities import User
from app.infrastructure.db.repositories.profile_repository import SqlProfileRepository
from app.infrastructure.db.session import get_db
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["profile"])


def get_profile_service(db: Session = Depends(get_db)) -> ProfileService:
    return ProfileService(profile_repo=SqlProfileRepository(db))


def _to_response(profile) -> ProfileResponse:
    return ProfileResponse(
        user_id=str(profile.user_id),
        display_name=profile.display_name,
        avatar_url=profile.avatar_url,
        bio=profile.bio,
        timezone=profile.timezone,
        updated_at=profile.updated_at,
    )


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    profile = service.get_profile(current_user.id)
    return _to_response(profile)


@router.patch("/me", response_model=ProfileResponse)
def update_my_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    profile = service.update_profile(
        current_user.id,
        display_name=payload.display_name,
        avatar_url=payload.avatar_url,
        bio=payload.bio,
        timezone_name=payload.timezone,
    )
    return _to_response(profile)
