"""PostgreSQL integration fixture using a disposable database and real Alembic migrations."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from vinami.shared.orm_registry import initialize_mappings

PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]


def _test_url() -> URL:
    source = make_url(os.environ["VINAMI_DATABASE_URL"])
    database = source.database or "vinami_acs"
    return source.set(database=f"{database}_sprint3_test")


def _drop_database(admin_url: URL, database_name: str) -> None:
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :database"
            ),
            {"database": database_name},
        )
        connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
    engine.dispose()


@pytest.fixture(scope="session")
def postgres_session_factory() -> Generator[sessionmaker[Session], None, None]:
    """Create a clean PostgreSQL database, migrate it, and remove it after integration tests."""
    if "VINAMI_DATABASE_URL" not in os.environ:
        pytest.skip("PostgreSQL integration tests require VINAMI_DATABASE_URL")
    test_url = _test_url()
    admin_url = test_url.set(database="postgres")
    _drop_database(admin_url, test_url.database or "vinami_acs_sprint3_test")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{test_url.database}"'))
    admin_engine.dispose()
    original_url = os.environ["VINAMI_DATABASE_URL"]
    os.environ["VINAMI_DATABASE_URL"] = test_url.render_as_string(hide_password=False)
    initialize_mappings()
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    engine = create_engine(test_url, pool_pre_ping=True)
    try:
        yield sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        engine.dispose()
        os.environ["VINAMI_DATABASE_URL"] = original_url
        _drop_database(admin_url, test_url.database or "vinami_acs_sprint3_test")
