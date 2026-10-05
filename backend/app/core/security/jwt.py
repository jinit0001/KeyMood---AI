"""
JWT issuance and verification — RS256 only (SECURITY.md §3), never HS256.

Access tokens carry {sub, role, scopes, type=access}. Refresh tokens carry
{sub, jti, type=refresh} and are never persisted in plaintext — only their
SHA-256 hash (see hash_refresh_token) is stored in `refresh_tokens.token_hash`,
alongside the `jti` for fast lookup, per the approved schema.
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import lru_cache
from typing import Any

import jwt as pyjwt
from jwt import InvalidTokenError as PyJWTInvalidTokenError, ExpiredSignatureError

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"
    GUARDIAN_CONSENT = "guardian_consent"


class InvalidTokenError(UnauthorizedError):
    """Token is malformed or fails signature/issuer verification."""
    error_code = "INVALID_TOKEN"


class TokenExpiredError(UnauthorizedError):
    """Token has expired."""
    error_code = "TOKEN_EXPIRED"


@lru_cache
def _keys(settings: Settings | None = None) -> tuple[str, str]:
    settings = settings or get_settings()
    return settings.load_jwt_private_key(), settings.load_jwt_public_key()


def _encode(payload: dict[str, Any]) -> str:
    settings = get_settings()
    private_key, _ = _keys()
    return pyjwt.encode(payload, private_key, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str, role: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "type": TokenType.ACCESS.value,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "iss": settings.JWT_ISSUER,
        "jti": str(uuid.uuid4()),
    }
    return _encode(payload)


def create_refresh_token(user_id: str) -> tuple[str, str, datetime]:
    """Returns (token, jti, expires_at). Caller persists token_hash + jti,
    never the raw token."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "type": TokenType.REFRESH.value,
        "iat": now,
        "exp": expires_at,
        "iss": settings.JWT_ISSUER,
        "jti": jti,
    }
    return _encode(payload), jti, expires_at


def create_email_verification_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": TokenType.EMAIL_VERIFICATION.value,
        "iat": now,
        "exp": now + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
        "iss": settings.JWT_ISSUER,
        "jti": str(uuid.uuid4()),
    }
    return _encode(payload)


def create_password_reset_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": TokenType.PASSWORD_RESET.value,
        "iat": now,
        "exp": now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        "iss": settings.JWT_ISSUER,
        "jti": str(uuid.uuid4()),
    }
    return _encode(payload)


def create_guardian_consent_token(guardian_id: str) -> str:
    """Stands in for real email/SMS delivery of the invite link, which
    isn't built. sub = guardian_id, not user_id — the guardian may not
    be a platform user at all."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": guardian_id,
        "type": TokenType.GUARDIAN_CONSENT.value,
        "iat": now,
        "exp": now + timedelta(days=7),
        "iss": settings.JWT_ISSUER,
        "jti": str(uuid.uuid4()),
    }
    return _encode(payload)


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    settings = get_settings()
    _, public_key = _keys()
    try:
        payload = pyjwt.decode(
            token,
            public_key,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
        )
    except ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except PyJWTInvalidTokenError as exc:
        raise InvalidTokenError() from exc

    if payload.get("type") != expected_type.value:
        raise InvalidTokenError(f"Expected a {expected_type.value} token.")

    return payload


# --- Hashing for at-rest storage ---
# Every token type above (refresh, email verification, password reset) is a
# signed, self-expiring JWT, but the RAW token is never persisted anywhere —
# only its SHA-256 hash, per SECURITY.md §3 ("stored hashed server-side").
# The DB row (refresh_tokens / email_verifications / password_resets) is
# also what makes a token *revocable and single-use*: a JWT's signature
# alone can't be un-issued, but its DB row can be marked revoked/consumed,
# which is checked in addition to signature+expiry on every use.

def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
