from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.infrastructure.db.base import Base

# Import every model module so Base.metadata is fully populated for
# autogenerate — required, not optional, or new tables silently won't
# be detected in future `alembic revision --autogenerate` runs.
from app.infrastructure.db.models import (  # noqa: F401
    data_export_request,
    email_verification,
    oauth_identity,
    password_reset,
    refresh_token,
    user,
    user_profile,
    user_settings,
)
from app.infrastructure.db import analytics_infra  # noqa: F401
from app.infrastructure.db import companion_infra  # noqa: F401
from app.infrastructure.db import emotion_infra  # noqa: F401
from app.infrastructure.db import journal_infra  # noqa: F401
from app.infrastructure.db import messaging_infra  # noqa: F401
from app.infrastructure.db import recommendation_infra  # noqa: F401
from app.infrastructure.db import social_infra  # noqa: F401
from app.infrastructure.db import sos_infra  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
