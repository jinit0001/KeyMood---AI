"""
FastAPI dependency wiring for Auth, per LLD.md §6: Depends() is the only
DI mechanism. Includes:
  - get_auth_service: assembles AuthService with real repositories
  - get_current_user: the authentication dependency every protected route
    across every future module will use
  - require_role: the generic authorization dependency (SECURITY.md §2)
"""
from uuid import UUID

from fastapi import Depends, Header, WebSocket
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError
from app.core.security import jwt as jwt_utils
from app.domain.auth.entities import User, UserRole
from app.infrastructure.db.repositories.email_verification_repository import SqlEmailVerificationRepository
from app.infrastructure.db.repositories.oauth_identity_repository import SqlOAuthIdentityRepository
from app.infrastructure.db.repositories.password_reset_repository import SqlPasswordResetRepository
from app.infrastructure.db.repositories.profile_initializer import SqlProfileInitializer
from app.infrastructure.db.repositories.refresh_token_repository import SqlRefreshTokenRepository
from app.infrastructure.db.repositories.user_repository import SqlUserRepository
from app.infrastructure.db.session import get_db
from app.infrastructure.notifications.email_sender import SmtpEmailSender
from app.infrastructure.oauth.google_provider import GoogleOAuthProvider
from app.services.auth_service import AuthService


def get_auth_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(
        user_repo=SqlUserRepository(db),
        oauth_repo=SqlOAuthIdentityRepository(db),
        email_verification_repo=SqlEmailVerificationRepository(db),
        password_reset_repo=SqlPasswordResetRepository(db),
        refresh_token_repo=SqlRefreshTokenRepository(db),
        profile_initializer=SqlProfileInitializer(db),
        email_sender=SmtpEmailSender(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_USE_TLS,
            from_address=settings.SMTP_FROM_ADDRESS,
        ),
        google_provider=GoogleOAuthProvider(settings.GOOGLE_CLIENT_ID),
        access_token_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        email_verification_expire_hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS,
        password_reset_expire_minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
        frontend_base_url=settings.FRONTEND_BASE_URL,
        auto_verify_email=settings.auto_verify_email,
    )


async def get_current_user(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> User:
    """The authentication dependency. Every protected route in every
    future module depends on this. Validates the access token's
    signature/type/expiry, then loads the current user row so status
    (suspended/deleted) is always checked fresh, not just trusted from
    the token payload."""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise jwt_utils.InvalidTokenError("Missing or malformed Authorization header.")

    payload = jwt_utils.decode_token(token, jwt_utils.TokenType.ACCESS)
    user_repo = SqlUserRepository(db)
    user = user_repo.get_by_id(UUID(payload["sub"]))
    if user is None or not user.is_active():
        raise jwt_utils.InvalidTokenError("User no longer active.")
    return user


def require_role(*allowed_roles: UserRole):
    """Generic authorization dependency (SECURITY.md §2: role-based access).
    Not Auth-specific — any future module's routes can depend on this,
    e.g. Depends(require_role(UserRole.ADMIN)) for /admin/* per API_SPEC.md §12."""

    async def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenError("You do not have permission to perform this action.")
        return current_user

    return _dependency


async def get_current_user_ws(websocket: WebSocket, db: Session = Depends(get_db)) -> User:
    """WS twin of get_current_user. Browsers can't set headers on the WS
    handshake, so this accepts Authorization header OR a `token` query
    param — gap-filled transport, same token validation either way."""
    auth = websocket.headers.get("authorization", "")
    scheme, _, header_token = auth.partition(" ")
    token = header_token if scheme.lower() == "bearer" else websocket.query_params.get("token", "")
    if not token:
        raise jwt_utils.InvalidTokenError("Missing access token.")
    payload = jwt_utils.decode_token(token, jwt_utils.TokenType.ACCESS)
    from app.infrastructure.db.repositories.user_repository import SqlUserRepository
    user = SqlUserRepository(db).get_by_id(UUID(payload["sub"]))
    if user is None or not user.is_active():
        raise jwt_utils.InvalidTokenError("User no longer active.")
    return user
