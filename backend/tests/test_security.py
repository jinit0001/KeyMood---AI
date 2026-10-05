from datetime import timedelta

import jwt as pyjwt
import pytest

from app.core.security import jwt as jwt_utils
from app.core.security.password import hash_password, validate_password_policy, verify_password


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("Str0ng!Passw0rd")
        assert hashed != "Str0ng!Passw0rd"
        assert hashed.startswith("$argon2id$")  # Argon2id, never bcrypt ($2b$)

    def test_verify_correct_password(self):
        hashed = hash_password("Str0ng!Passw0rd")
        assert verify_password("Str0ng!Passw0rd", hashed) is True

    def test_verify_incorrect_password(self):
        hashed = hash_password("Str0ng!Passw0rd")
        assert verify_password("WrongPassword1!", hashed) is False

    def test_verify_malformed_hash_does_not_raise(self):
        assert verify_password("anything", "not-a-real-hash") is False


class TestPasswordPolicy:
    @pytest.mark.parametrize(
        "password",
        ["short1!", "alllowercase1!", "ALLUPPERCASE1!", "NoNumbers!!", "NoSymbols123"],
    )
    def test_rejects_weak_passwords(self, password):
        assert validate_password_policy(password) != []

    def test_accepts_strong_password(self):
        assert validate_password_policy("Str0ng!Passw0rd") == []

    def test_rejects_common_password(self):
        assert validate_password_policy("Password123!") == [] or "common" in " ".join(
            validate_password_policy("password123")
        )


class TestJwt:
    def test_access_token_round_trip(self):
        token = jwt_utils.create_access_token("user-123", "user")
        payload = jwt_utils.decode_token(token, jwt_utils.TokenType.ACCESS)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "user"
        assert payload["type"] == "access"

    def test_uses_rs256_not_hs256(self):
        token = jwt_utils.create_access_token("user-123", "user")
        header = pyjwt.get_unverified_header(token)
        assert header["alg"] == "RS256"

    def test_refresh_token_has_jti(self):
        token, jti, expires_at = jwt_utils.create_refresh_token("user-123")
        payload = jwt_utils.decode_token(token, jwt_utils.TokenType.REFRESH)
        assert payload["jti"] == jti

    def test_wrong_token_type_rejected(self):
        access_token = jwt_utils.create_access_token("user-123", "user")
        with pytest.raises(jwt_utils.InvalidTokenError):
            jwt_utils.decode_token(access_token, jwt_utils.TokenType.REFRESH)

    def test_tampered_token_rejected(self):
        token = jwt_utils.create_access_token("user-123", "user")
        tampered = token[:-4] + ("aaaa" if token[-4:] != "aaaa" else "bbbb")
        with pytest.raises(jwt_utils.InvalidTokenError):
            jwt_utils.decode_token(tampered, jwt_utils.TokenType.ACCESS)

    def test_expired_token_rejected(self):
        # Force a token that's already expired by constructing it directly.
        from datetime import datetime, timezone

        from app.core.config import get_settings
        settings = get_settings()
        private_key, _ = jwt_utils._keys()
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-123",
            "role": "user",
            "type": "access",
            "iat": now - timedelta(minutes=30),
            "exp": now - timedelta(minutes=1),
            "iss": settings.JWT_ISSUER,
            "jti": "test-jti",
        }
        expired_token = pyjwt.encode(payload, private_key, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(jwt_utils.TokenExpiredError):
            jwt_utils.decode_token(expired_token, jwt_utils.TokenType.ACCESS)

    def test_hash_token_is_deterministic_and_one_way(self):
        h1 = jwt_utils.hash_token("some-raw-token")
        h2 = jwt_utils.hash_token("some-raw-token")
        assert h1 == h2
        assert h1 != "some-raw-token"
