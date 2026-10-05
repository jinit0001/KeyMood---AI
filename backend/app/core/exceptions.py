"""
Domain-level exceptions.

Per LLD.md §7 (validation flow): domain rule violations raise these from
the service layer. They carry no HTTP knowledge. `error_handlers.py` is
the single place that maps them to the API_SPEC.md error envelope.
error_code values match API_SPEC.md's "Standard Error Codes" table and
the specific per-endpoint error codes it lists.
"""


class AppError(Exception):
    http_status: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str | None = None, details: dict | None = None):
        self.message = message or self.__class__.__doc__ or "An error occurred"
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(AppError):
    """Schema/field validation failed."""
    http_status = 400
    error_code = "VALIDATION_ERROR"


class UnauthorizedError(AppError):
    """Missing, invalid, or expired token."""
    http_status = 401
    error_code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    """Authenticated but not permitted."""
    http_status = 403
    error_code = "FORBIDDEN"


class NotFoundError(AppError):
    """Resource does not exist or is not visible to the caller."""
    http_status = 404
    error_code = "NOT_FOUND"


class ConflictError(AppError):
    """Duplicate or state conflict."""
    http_status = 409
    error_code = "CONFLICT"


class RateLimitedError(AppError):
    """Too many requests."""
    http_status = 429
    error_code = "RATE_LIMITED"

    def __init__(self, retry_after_seconds: int, message: str | None = None):
        super().__init__(message, details={"retry_after": retry_after_seconds})
        self.retry_after_seconds = retry_after_seconds


# --- Auth-specific, mapped to exact API_SPEC.md codes ---

class EmailAlreadyExistsError(ConflictError):
    """This email is already registered."""
    error_code = "EMAIL_ALREADY_EXISTS"


class InvalidCredentialsError(UnauthorizedError):
    """Email or password is incorrect."""
    error_code = "INVALID_CREDENTIALS"


class EmailNotVerifiedError(ForbiddenError):
    """Email address has not been verified yet."""
    error_code = "EMAIL_NOT_VERIFIED"


class AccountSuspendedError(ForbiddenError):
    """Account has been suspended."""
    error_code = "ACCOUNT_SUSPENDED"


class TokenInvalidOrExpiredError(AppError):
    """Token is invalid, malformed, or expired."""
    http_status = 400
    error_code = "TOKEN_INVALID_OR_EXPIRED"


class RefreshTokenInvalidOrRevokedError(UnauthorizedError):
    """Refresh token is invalid, expired, or has been revoked."""
    error_code = "REFRESH_TOKEN_INVALID_OR_REVOKED"


class InvalidGoogleTokenError(UnauthorizedError):
    """Google ID token failed verification."""
    error_code = "INVALID_GOOGLE_TOKEN"


class ProfileNotFoundError(NotFoundError):
    """User profile does not exist."""
    error_code = "PROFILE_NOT_FOUND"


class ConsentRequiredError(ForbiddenError):
    """Keystroke monitoring consent not granted. API_SPEC.md §6: 403 CONSENT_REQUIRED."""
    error_code = "CONSENT_REQUIRED"


class GuardianNotFoundError(NotFoundError):
    error_code = "GUARDIAN_NOT_FOUND"


class RiskEventNotFoundError(NotFoundError):
    error_code = "RISK_EVENT_NOT_FOUND"


class JournalEntryNotFoundError(NotFoundError):
    error_code = "JOURNAL_ENTRY_NOT_FOUND"
