"""
Password hashing — Argon2id only (SECURITY.md §1/§4). Bcrypt is not used
anywhere in this codebase.
"""
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError, VerificationError
from argon2.low_level import Type as Argon2Type

from app.core.config import get_settings

_settings = get_settings()

_hasher = PasswordHasher(
    time_cost=_settings.ARGON2_TIME_COST,
    memory_cost=_settings.ARGON2_MEMORY_COST_KIB,
    parallelism=_settings.ARGON2_PARALLELISM,
    type=Argon2Type.ID,  # Argon2id explicitly, not relying on the library default
)

# Common-password blocklist check per SECURITY.md §1. A minimal representative
# set is embedded so registration validation works standalone offline; in
# production this should be backed by a larger list (e.g., a maintained
# top-10k breached-password corpus loaded at startup).
_COMMON_PASSWORDS = {
    "password123", "qwerty12345", "letmein123", "welcome12345",
    "password1234", "iloveyou123", "admin1234567",
}


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """Lets the service layer transparently upgrade hashes if Argon2
    parameters are tightened later (SECURITY.md: 'reviewed periodically')."""
    return _hasher.check_needs_rehash(password_hash)


def validate_password_policy(password: str) -> list[str]:
    """Returns a list of policy violations (empty list = valid).
    Per SECURITY.md §1: min 10 chars, mixed case, number, symbol,
    checked against a common-password blocklist."""
    errors: list[str] = []
    if len(password) < _settings.PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {_settings.PASSWORD_MIN_LENGTH} characters.")
    if not any(c.islower() for c in password):
        errors.append("Password must contain a lowercase letter.")
    if not any(c.isupper() for c in password):
        errors.append("Password must contain an uppercase letter.")
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain a number.")
    if not any(not c.isalnum() for c in password):
        errors.append("Password must contain a symbol.")
    if password.lower() in _COMMON_PASSWORDS:
        errors.append("Password is too common. Choose a less predictable password.")
    return errors
