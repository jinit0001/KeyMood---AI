from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import InvalidCredentialsError, ValidationError
from app.core.security.password import hash_password
from app.domain.auth.entities import User, UserRole, UserStatus
from app.services.settings_service import SettingsService
from tests.fakes import FakeRefreshTokenRepository, FakeUserRepository
from tests.fakes_profile import FakeDataExportRepository, FakeSettingsRepository

PASSWORD = "Str0ng!Passw0rd"


def _make_user(user_id) -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=user_id,
        email="user@example.com",
        password_hash=hash_password(PASSWORD),
        email_verified=True,
        status=UserStatus.ACTIVE,
        role=UserRole.USER,
        privacy_consent_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def settings_repo():
    return FakeSettingsRepository()


@pytest.fixture
def export_repo():
    return FakeDataExportRepository()


@pytest.fixture
def user_repo():
    return FakeUserRepository()


@pytest.fixture
def refresh_repo():
    return FakeRefreshTokenRepository()


@pytest.fixture
def service(settings_repo, export_repo, user_repo, refresh_repo):
    return SettingsService(
        settings_repo=settings_repo,
        export_repo=export_repo,
        user_repo=user_repo,
        refresh_token_repo=refresh_repo,
    )


class TestPrivacySettings:
    def test_defaults_are_all_true(self, service):
        user_id = uuid4()
        privacy = service.get_privacy(user_id)
        assert privacy.keystroke_analysis is True
        assert privacy.guardian_sharing is True

    def test_update_single_toggle(self, service):
        user_id = uuid4()
        updated = service.update_privacy(user_id, keystroke_analysis=False)
        assert updated.keystroke_analysis is False
        # Untouched fields keep their defaults.
        assert updated.journal_analysis is True

    def test_update_persists_across_calls(self, service):
        user_id = uuid4()
        service.update_privacy(user_id, companion_memory=False)
        privacy = service.get_privacy(user_id)
        assert privacy.companion_memory is False


class TestNotificationSettings:
    def test_defaults_are_all_true(self, service):
        notifications = service.get_notifications(uuid4())
        assert notifications.sos_alerts is True

    def test_update_single_toggle(self, service):
        user_id = uuid4()
        updated = service.update_notifications(user_id, messages=False)
        assert updated.messages is False
        assert updated.friend_requests is True


class TestAIPreferences:
    def test_defaults(self, service):
        prefs = service.get_ai_preferences(uuid4())
        assert prefs.companion_tone == "supportive"
        assert prefs.coaching_frequency == "normal"
        assert prefs.feature_opt_outs == []

    def test_update_valid_tone_and_frequency(self, service):
        user_id = uuid4()
        updated = service.update_ai_preferences(user_id, companion_tone="direct", coaching_frequency="high")
        assert updated.companion_tone == "direct"
        assert updated.coaching_frequency == "high"

    def test_update_feature_opt_outs(self, service):
        user_id = uuid4()
        updated = service.update_ai_preferences(user_id, feature_opt_outs=["voice_journaling"])
        assert updated.feature_opt_outs == ["voice_journaling"]

    def test_invalid_companion_tone_rejected(self, service):
        with pytest.raises(ValidationError):
            service.update_ai_preferences(uuid4(), companion_tone="sarcastic")

    def test_invalid_coaching_frequency_rejected(self, service):
        with pytest.raises(ValidationError):
            service.update_ai_preferences(uuid4(), coaching_frequency="extreme")


class TestDataExport:
    def test_request_export_creates_pending_record(self, service, export_repo):
        user_id = uuid4()
        request = service.request_export(user_id)

        assert request.status == "pending"
        assert request.user_id == user_id
        assert len(export_repo.requests) == 1


class TestDeleteAccount:
    def test_correct_password_deletes_account_and_revokes_sessions(
        self, service, user_repo, refresh_repo
    ):
        user_id = uuid4()
        user_repo.add(_make_user(user_id))
        from app.domain.auth.entities import RefreshToken

        token = RefreshToken(
            id=uuid4(),
            user_id=user_id,
            token_hash="hash",
            jti=uuid4(),
            expires_at=datetime.now(timezone.utc),
            revoked_at=None,
            created_at=datetime.now(timezone.utc),
        )
        refresh_repo.add(token)

        service.delete_account(user_id, PASSWORD)

        stored_user = user_repo.get_by_id(user_id)
        assert stored_user.status == UserStatus.DELETED
        assert stored_user.deleted_at is not None
        assert refresh_repo.get_by_jti(token.jti).revoked_at is not None

    def test_wrong_password_rejected(self, service, user_repo):
        user_id = uuid4()
        user_repo.add(_make_user(user_id))

        with pytest.raises(InvalidCredentialsError):
            service.delete_account(user_id, "wrong-password")

    def test_nonexistent_user_rejected(self, service):
        with pytest.raises(InvalidCredentialsError):
            service.delete_account(uuid4(), PASSWORD)
