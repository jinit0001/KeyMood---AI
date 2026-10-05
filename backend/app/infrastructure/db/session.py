from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False, future=True)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — one session per request, always closed.

    Commits on success, rolls back on any exception. Without this,
    SQLAlchemy's default behavior on session.close() is to roll back any
    pending transaction — meaning every write in the app would silently
    vanish after the request completed. Confirmed by testing an actual
    HTTP round-trip against real Postgres (not fakes): register returned
    201 with a real user_id, but the row was absent immediately after.
    """
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
