import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_KEYS = _ROOT / "keys"

# Test environment must be set BEFORE any `app.*` module is imported,
# since app.core.config.get_settings() is called at import time in
# several modules (router.py, main.py).
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("JWT_PRIVATE_KEY_PATH", str(_KEYS / "dev_jwt_private.pem"))
os.environ.setdefault("JWT_PUBLIC_KEY_PATH", str(_KEYS / "dev_jwt_public.pem"))
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")

import pytest  # noqa: E402

from app.services.auth_service import AuthService  # noqa: E402
from tests.fakes import (  # noqa: E402
    FakeEmailSender,
    FakeEmailVerificationRepository,
    FakeGoogleOAuthProvider,
    FakeOAuthIdentityRepository,
    FakePasswordResetRepository,
    FakeProfileInitializer,
    FakeRefreshTokenRepository,
    FakeUserRepository,
)


@pytest.fixture
def fake_repos():
    return {
        "user_repo": FakeUserRepository(),
        "oauth_repo": FakeOAuthIdentityRepository(),
        "email_verification_repo": FakeEmailVerificationRepository(),
        "password_reset_repo": FakePasswordResetRepository(),
        "refresh_token_repo": FakeRefreshTokenRepository(),
        "profile_initializer": FakeProfileInitializer(),
    }


@pytest.fixture
def fake_email_sender():
    return FakeEmailSender()


@pytest.fixture
def auth_service(fake_repos, fake_email_sender):
    return AuthService(
        user_repo=fake_repos["user_repo"],
        oauth_repo=fake_repos["oauth_repo"],
        email_verification_repo=fake_repos["email_verification_repo"],
        password_reset_repo=fake_repos["password_reset_repo"],
        refresh_token_repo=fake_repos["refresh_token_repo"],
        profile_initializer=fake_repos["profile_initializer"],
        email_sender=fake_email_sender,
        google_provider=FakeGoogleOAuthProvider(),
        access_token_expire_minutes=15,
        email_verification_expire_hours=24,
        password_reset_expire_minutes=30,
        frontend_base_url="http://localhost:5173",
    )


VALID_PASSWORD = "Str0ng!Passw0rd"
