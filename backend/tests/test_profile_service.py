from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import ProfileNotFoundError, ValidationError
from app.domain.profile.entities import Profile
from app.services.profile_service import ProfileService, validate_profile_fields
from tests.fakes_profile import FakeProfileRepository


def _make_profile(user_id) -> Profile:
    return Profile(
        user_id=user_id,
        display_name="Jinit",
        avatar_url=None,
        bio=None,
        timezone="UTC",
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def repo():
    return FakeProfileRepository()


@pytest.fixture
def service(repo):
    return ProfileService(profile_repo=repo)


class TestGetProfile:
    def test_returns_existing_profile(self, service, repo):
        user_id = uuid4()
        repo.seed(_make_profile(user_id))

        profile = service.get_profile(user_id)

        assert profile.display_name == "Jinit"

    def test_missing_profile_raises_not_found(self, service):
        with pytest.raises(ProfileNotFoundError):
            service.get_profile(uuid4())


class TestUpdateProfile:
    def test_updates_display_name(self, service, repo):
        user_id = uuid4()
        repo.seed(_make_profile(user_id))

        updated = service.update_profile(user_id, display_name="New Name")

        assert updated.display_name == "New Name"
        assert repo.get_by_user_id(user_id).display_name == "New Name"

    def test_updates_bio_avatar_timezone(self, service, repo):
        user_id = uuid4()
        repo.seed(_make_profile(user_id))

        updated = service.update_profile(
            user_id, bio="Building KeyMood AI", avatar_url="https://example.com/a.png", timezone_name="Asia/Kolkata"
        )

        assert updated.bio == "Building KeyMood AI"
        assert updated.avatar_url == "https://example.com/a.png"
        assert updated.timezone == "Asia/Kolkata"

    def test_partial_update_leaves_other_fields_untouched(self, service, repo):
        user_id = uuid4()
        profile = _make_profile(user_id)
        profile.bio = "original bio"
        repo.seed(profile)

        updated = service.update_profile(user_id, display_name="Only Name Changed")

        assert updated.display_name == "Only Name Changed"
        assert updated.bio == "original bio"

    def test_empty_display_name_rejected(self, service, repo):
        user_id = uuid4()
        repo.seed(_make_profile(user_id))

        with pytest.raises(ValidationError):
            service.update_profile(user_id, display_name="   ")

    def test_display_name_over_max_length_rejected(self, service, repo):
        user_id = uuid4()
        repo.seed(_make_profile(user_id))

        with pytest.raises(ValidationError):
            service.update_profile(user_id, display_name="x" * 81)

    def test_bio_over_max_length_rejected(self, service, repo):
        user_id = uuid4()
        repo.seed(_make_profile(user_id))

        with pytest.raises(ValidationError):
            service.update_profile(user_id, bio="x" * 301)

    def test_update_nonexistent_profile_raises_not_found(self, service):
        with pytest.raises(ProfileNotFoundError):
            service.update_profile(uuid4(), display_name="Ghost")


class TestValidateProfileFields:
    def test_valid_fields_pass(self):
        assert validate_profile_fields("Name", "short bio") == []

    def test_none_fields_are_skipped(self):
        assert validate_profile_fields(None, None) == []

    def test_max_length_boundary_accepted(self):
        assert validate_profile_fields("x" * 80, "y" * 300) == []
