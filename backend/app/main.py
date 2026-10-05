from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth.router import router as auth_router
from app.api.v1.emotion import router as emotion_router
from app.api.v1.insights import analytics_router, recommendations_router
from app.api.v1.companion import router as companion_router
from app.api.v1.journal import router as journal_router
from app.api.v1.messaging import router as messaging_router
from app.api.v1.social import router as social_router
from app.api.v1.profile.router import router as profile_router
from app.api.v1.settings.router import router as settings_router
from app.api.v1.sos import router as sos_router
from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.core.logging_config import configure_logging
from app.core.middleware import RequestContextMiddleware

settings = get_settings()
configure_logging(settings.LOG_LEVEL)

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)

register_error_handlers(app)

app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(profile_router, prefix=settings.API_V1_PREFIX)
app.include_router(settings_router, prefix=settings.API_V1_PREFIX)
app.include_router(emotion_router, prefix=settings.API_V1_PREFIX)
app.include_router(sos_router, prefix=settings.API_V1_PREFIX)
app.include_router(journal_router, prefix=settings.API_V1_PREFIX)
app.include_router(recommendations_router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics_router, prefix=settings.API_V1_PREFIX)
app.include_router(social_router, prefix=settings.API_V1_PREFIX)
app.include_router(messaging_router, prefix=settings.API_V1_PREFIX)
app.include_router(companion_router, prefix=settings.API_V1_PREFIX)


@app.get("/health/liveness", tags=["health"])
def liveness() -> dict:
    """Per DEPLOYMENT.md §5 — process is up, no dependency checks."""
    return {"status": "ok"}


@app.get("/health/readiness", tags=["health"])
def readiness() -> dict:
    """Per DEPLOYMENT.md §5 — checks DB connectivity."""
    from sqlalchemy import text

    from app.infrastructure.db.session import get_engine

    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:  # noqa: BLE001 — readiness probe must not crash
        return {"status": "not_ready", "database": "error", "detail": str(exc)}
