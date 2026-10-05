"""
SettingsService — orchestrates Settings use cases (API_SPEC.md §11).
Reuses Auth's UserRepository/RefreshTokenRepository Protocols directly
for account deletion (revoking sessions, marking the user deleted) —
this is a later module depending on Auth's foundational domain, not a
new abstraction duplicating it.
"""
import logging
from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.exceptions import InvalidCredentialsError, ValidationError
from app.core.security.password import verify_password
from app.domain.auth.entities import UserStatus
from app.domain.auth.repositories import RefreshTokenRepository, UserRepository
from app.domain.profile.entities import AIPreferences, DataExportRequest, NotificationSettings, PrivacySettings
from app.domain.profile.ports import DataExportRepository, SettingsRepository

logger = logging.getLogger("keymood.settings")

VALID_COMPANION_TONES = {"supportive", "direct", "playful"}
VALID_COACHING_FREQUENCIES = {"low", "normal", "high"}


class SettingsService:
    def __init__(
        self,
        settings_repo: SettingsRepository,
        export_repo: DataExportRepository,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
    ):
        self._settings = settings_repo
        self._exports = export_repo
        self._users = user_repo
        self._refresh_tokens = refresh_token_repo

    def _get_or_create(self, user_id: UUID):
        settings = self._settings.get_by_user_id(user_id)
        if settings is None:
            settings = self._settings.create_default(user_id)
        return settings

    # --- Privacy ---
    def get_privacy(self, user_id: UUID) -> PrivacySettings:
        return self._get_or_create(user_id).privacy

    def update_privacy(self, user_id: UUID, **changes) -> PrivacySettings:
        settings = self._get_or_create(user_id)
        updates = {k: v for k, v in changes.items() if v is not None}
        settings.privacy = replace(settings.privacy, **updates)
        settings.updated_at = datetime.now(timezone.utc)
        self._settings.update(settings)
        logger.info("privacy_settings_updated", extra={"user_id": str(user_id)})
        return settings.privacy

    # --- Notifications ---
    def get_notifications(self, user_id: UUID) -> NotificationSettings:
        return self._get_or_create(user_id).notifications

    def update_notifications(self, user_id: UUID, **changes) -> NotificationSettings:
        settings = self._get_or_create(user_id)
        updates = {k: v for k, v in changes.items() if v is not None}
        settings.notifications = replace(settings.notifications, **updates)
        settings.updated_at = datetime.now(timezone.utc)
        self._settings.update(settings)
        logger.info("notification_settings_updated", extra={"user_id": str(user_id)})
        return settings.notifications

    # --- AI preferences ---
    def get_ai_preferences(self, user_id: UUID) -> AIPreferences:
        return self._get_or_create(user_id).ai_preferences

    def update_ai_preferences(
        self,
        user_id: UUID,
        companion_tone: str | None = None,
        coaching_frequency: str | None = None,
        feature_opt_outs: list[str] | None = None,
    ) -> AIPreferences:
        errors: list[str] = []
        if companion_tone is not None and companion_tone not in VALID_COMPANION_TONES:
            errors.append(f"companion_tone must be one of {sorted(VALID_COMPANION_TONES)}.")
        if coaching_frequency is not None and coaching_frequency not in VALID_COACHING_FREQUENCIES:
            errors.append(f"coaching_frequency must be one of {sorted(VALID_COACHING_FREQUENCIES)}.")
        if errors:
            raise ValidationError("AI preferences update failed validation.", {"errors": errors})

        settings = self._get_or_create(user_id)
        current = settings.ai_preferences
        settings.ai_preferences = AIPreferences(
            companion_tone=companion_tone if companion_tone is not None else current.companion_tone,
            coaching_frequency=(
                coaching_frequency if coaching_frequency is not None else current.coaching_frequency
            ),
            feature_opt_outs=feature_opt_outs if feature_opt_outs is not None else current.feature_opt_outs,
        )
        settings.updated_at = datetime.now(timezone.utc)
        self._settings.update(settings)
        logger.info("ai_preferences_updated", extra={"user_id": str(user_id)})
        return settings.ai_preferences

    # --- Data export ---
    def request_export(self, user_id: UUID) -> DataExportRequest:
        """API_SPEC.md §11: '202 Accepted, async job, delivered via secure
        download link, expires in 24h.' KNOWN LIMITATION: no real
        background worker or file-generation exists yet — this creates a
        real request record (status=pending) so the contract shape is
        genuine and testable, but nothing ever completes it. Wiring an
        actual export job is flagged here as a follow-up, not silently
        skipped or faked as already working."""
        now = datetime.now(timezone.utc)
        request = DataExportRequest(
            id=uuid4(),
            user_id=user_id,
            status="pending",
            download_url=None,
            expires_at=None,
            requested_at=now,
            completed_at=None,
        )
        self._exports.add(request)
        logger.info("data_export_requested", extra={"user_id": str(user_id)})
        return request

    # --- Account deletion ---
    def delete_account(self, user_id: UUID, password: str) -> None:
        """API_SPEC.md §11: 'requires password re-confirmation; soft-delete
        then scheduled hard purge.' KNOWN LIMITATION: only soft-delete +
        session revocation happen here; the actual 30-day hard-purge job
        (SECURITY.md §9) is an ops/scheduler concern not built by this
        module. KNOWN GAP: OAuth-only accounts (password_hash is None)
        cannot pass password re-confirmation as specified — not addressed
        by API_SPEC.md, flagged here rather than silently handled."""
        user = self._users.get_by_id(user_id)
        if user is None or user.password_hash is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Password does not match.")

        now = datetime.now(timezone.utc)
        user.status = UserStatus.DELETED
        user.deleted_at = now
        user.updated_at = now
        self._users.update(user)
        self._refresh_tokens.revoke_all_for_user(user.id, now)
        logger.info("account_deleted", extra={"user_id": str(user_id)})
