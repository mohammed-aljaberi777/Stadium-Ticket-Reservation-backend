from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.core.config import settings

# Importing Base from the models package registers ALL 9 models, so
# Base.metadata knows about every table. This is what autogenerate compares against.
from app.models import Base

# Alembic Config object — reads values from alembic.ini
config = context.config

# Inject our database URL (sync psycopg2 driver) from application settings,
# so we never hard-code credentials in alembic.ini.
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

# Configure Python logging from the ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata autogenerate uses to detect what tables/columns should exist
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to a script instead of running against a live DB."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
