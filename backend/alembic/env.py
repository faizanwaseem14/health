"""
Alembic's setup file - this is what runs whenever you do
`alembic revision --autogenerate` or `alembic upgrade head`.

We only changed two things from Alembic's default template:
  1. The database URL comes from our own app.config (your .env file)
     instead of being hardcoded in alembic.ini - so there's still only
     ONE place your real DATABASE_URL lives.
  2. target_metadata points at our models (app.models), so Alembic knows
     what the schema is SUPPOSED to look like and can compare it against
     what's actually in the database.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import all 11 models so Base.metadata knows about every table before
# Alembic compares it against the real database.
from app import models  # noqa: F401
from app.config import settings
from app.database import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use the real database URL from our .env-based settings, not from
# alembic.ini (which is committed to git and must never hold a secret).
config.set_main_option("sqlalchemy.url", settings.database_url)

# This tells `alembic revision --autogenerate` what our tables SHOULD
# look like, so it can diff that against the real database.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
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
