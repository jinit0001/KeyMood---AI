from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base. Every module's SQLAlchemy models inherit
    from this so Alembic autogenerate sees a single metadata object."""
    pass
