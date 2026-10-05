"""
Settings routes. Paths, methods, status codes match API_SPEC.md §11
exactly.
"""
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.settings.schemas import (
    AIPreferencesResponse,
    AIPreferencesUpdateRequest,
    DeleteAccountRequest,
    ExportResponse,
    NotificationSettingsResponse,
    NotificationSettingsUpdateRequest,
    PrivacySettingsResponse,
    PrivacySettingsUpdateRequest,
)
from app.domain.auth.entities import User
from app.infrastructure.db.repositories.data_export_repository import SqlDataExportRepository
from app.infrastructure.db.repositories.refresh_token_repository import SqlRefreshTokenRepository
from app.infrastructure.db.repositories.settings_repository import SqlSettingsRepository
from app.infrastructure.db.repositories.user_repository import SqlUserRepository
from app.infrastructure.db.session import get_db
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


def get_settings_service(db: Session = Depends(get_db)) -> SettingsService:
    return SettingsService(
        settings_repo=SqlSettingsRepository(db),
        export_repo=SqlDataExportRepository(db),
        user_repo=SqlUserRepository(db),
        refresh_token_repo=SqlRefreshTokenRepository(db),
    )


# --- Privacy ---
@router.get("/privacy", response_model=PrivacySettingsResponse)
def get_privacy(
    current_user: User = Depends(get_current_user),
    service: SettingsService = Depends(get_settings_service),
) -> PrivacySettingsResponse:
    privacy = service.get_privacy(current_user.id)
    return PrivacySettingsResponse(**privacy.__dict__)


@router.patch("/privacy", response_model=PrivacySettingsResponse)
def update_privacy(
    payload: PrivacySettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: SettingsService = Depends(get_settings_service),
) -> PrivacySettingsResponse:
    privacy = service.update_privacy(current_user.id, **payload.model_dump())
    return PrivacySettingsResponse(**privacy.__dict__)


# --- Notifications ---
@router.get("/notifications", response_model=NotificationSettingsResponse)
def get_notifications(
    current_user: User = Depends(get_current_user),
    service: SettingsService = Depends(get_settings_service),
) -> NotificationSettingsResponse:
    notifications = service.get_notifications(current_user.id)
    return NotificationSettingsResponse(**notifications.__dict__)


@router.patch("/notifications", response_model=NotificationSettingsResponse)
def update_notifications(
    payload: NotificationSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: SettingsService = Depends(get_settings_service),
) -> NotificationSettingsResponse:
    notifications = service.update_notifications(current_user.id, **payload.model_dump())
    return NotificationSettingsResponse(**notifications.__dict__)


# --- AI preferences ---
@router.get("/ai-preferences", response_model=AIPreferencesResponse)
def get_ai_preferences(
    current_user: User = Depends(get_current_user),
    service: SettingsService = Depends(get_settings_service),
) -> AIPreferencesResponse:
    prefs = service.get_ai_preferences(current_user.id)
    return AIPreferencesResponse(**prefs.__dict__)


@router.patch("/ai-preferences", response_model=AIPreferencesResponse)
def update_ai_preferences(
    payload: AIPreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: SettingsService = Depends(get_settings_service),
) -> AIPreferencesResponse:
    prefs = service.update_ai_preferences(
        current_user.id,
        companion_tone=payload.companion_tone,
        coaching_frequency=payload.coaching_frequency,
        feature_opt_outs=payload.feature_opt_outs,
    )
    return AIPreferencesResponse(**prefs.__dict__)


# --- Export ---
@router.post("/export", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED)
def request_export(
    current_user: User = Depends(get_current_user),
    service: SettingsService = Depends(get_settings_service),
) -> ExportResponse:
    request = service.request_export(current_user.id)
    return ExportResponse(
        request_id=str(request.id), status=request.status, requested_at=request.requested_at
    )


# --- Account deletion ---
@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    service: SettingsService = Depends(get_settings_service),
) -> Response:
    service.delete_account(current_user.id, payload.password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
