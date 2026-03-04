import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.database import Base
from app.models import (  # noqa: F401
    APIKey,
    AuditLog,
    Environment,
    Flag,
    FlagValue,
    Project,
    UsageRecord,
    User,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Allow overriding the database URL via environment variable.
# Converts the async aiosqlite URL to a sync sqlite URL for Alembic.
db_url_env = os.environ.get("FLAGDROP_DATABASE_URL")
if db_url_env:
    sync_url = db_url_env.replace("sqlite+aiosqlite", "sqlite")
    config.set_main_option("sqlalchemy.url", sync_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
