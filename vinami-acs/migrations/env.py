"""Alembic environment for the VinAMI ACS system-of-record schema."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from vinami.shared.config import Settings
from vinami.shared.orm_registry import initialize_mappings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = initialize_mappings()


def database_url() -> str:
    """Use the same validated connection string as the application factory."""
    return Settings().database_url


def run_migrations_offline() -> None:
    """Configure Alembic for SQL-script generation without a live database."""
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Configure Alembic against a live database connection."""
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
