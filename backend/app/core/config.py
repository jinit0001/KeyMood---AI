"""
Central application configuration.

Every secret is loaded from the environment — never hard-coded. In
development, JWT_PRIVATE_KEY_PATH/JWT_PUBLIC_KEY_PATH point at local PEM
files. In production, the same two env vars are populated by whatever
secrets manager the deployment platform uses (DEPLOYMENT.md) — the
application code does not change between environments, only where the
env vars are injected from.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "KeyMood AI Backend"
    APP_ENV: str = "development"  # development | staging | production
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # --- Database ---
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "keymood"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- Redis (rate limiting only for MVP — no WS pub/sub yet) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- JWT (RS256) ---
    JWT_PRIVATE_KEY_PATH: str
    JWT_PUBLIC_KEY_PATH: str
    JWT_ALGORITHM: str = "RS256"
    JWT_ISSUER: str = "keymood-ai"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    @field_validator("JWT_PRIVATE_KEY_PATH", "JWT_PUBLIC_KEY_PATH")
    @classmethod
    def _validate_key_path(cls, v: str) -> str:
        if not v:
            raise ValueError("JWT key path must not be empty")
        return v

    def load_jwt_private_key(self) -> str:
        return Path(self.JWT_PRIVATE_KEY_PATH).read_text()

    def load_jwt_public_key(self) -> str:
        return Path(self.JWT_PUBLIC_KEY_PATH).read_text()

    # --- Argon2id ---
    ARGON2_TIME_COST: int = 3
    ARGON2_MEMORY_COST_KIB: int = 65536  # 64 MiB
    ARGON2_PARALLELISM: int = 2

    # --- Password policy ---
    PASSWORD_MIN_LENGTH: int = 10

    # --- Rate limiting (per API_SPEC.md §Auth) ---
    RATE_LIMIT_REGISTER_PER_MIN: int = 5
    RATE_LIMIT_LOGIN_PER_MIN: int = 10
    RATE_LIMIT_FORGOT_PASSWORD_PER_MIN: int = 3
    RATE_LIMIT_DEFAULT_PER_MIN: int = 100

    # --- Google OAuth ---
    GOOGLE_CLIENT_ID: str = ""

    # --- Dev convenience ---
    # When true AND APP_ENV == "development", new accounts are marked
    # email-verified immediately and no verification email is sent, so the
    # app runs locally without an SMTP server. Ignored in any other APP_ENV.
    DEV_AUTO_VERIFY_EMAIL: bool = False

    @property
    def auto_verify_email(self) -> bool:
        return self.DEV_AUTO_VERIFY_EMAIL and self.APP_ENV == "development"

    # --- Frontend links (for emails) ---
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # --- Logging ---
    LOG_LEVEL: str = "INFO"

    # --- SMTP (email sender) ---
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = False
    SMTP_FROM_ADDRESS: str = "no-reply@keymood.ai"


@lru_cache
def get_settings() -> Settings:
    return Settings()
