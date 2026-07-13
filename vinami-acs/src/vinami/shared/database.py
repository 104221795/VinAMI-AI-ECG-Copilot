"""SQLAlchemy engine and session infrastructure for the future system of record."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from vinami.shared.config import Settings
from vinami.shared.schema import CRITICAL_TABLES, EXPECTED_ALEMBIC_HEAD


class SchemaNotReadyError(RuntimeError):
    """Raised when PostgreSQL is reachable but the application schema is not ready."""


@dataclass(slots=True)
class Database:
    """Own a SQLAlchemy engine and explicit session factory outside domain code."""

    engine: Engine
    session_factory: sessionmaker[Session]

    @classmethod
    def from_settings(cls, settings: Settings) -> Database:
        """Build a connection pool from validated runtime configuration."""
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        return cls(engine=engine, session_factory=sessionmaker(bind=engine, expire_on_commit=False))

    def probe(self) -> None:
        """Raise an infrastructure error when PostgreSQL cannot answer a basic query."""
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def probe_readiness(self) -> None:
        """Verify connectivity, critical tables, and the exact expected Alembic head."""
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            tables = set(inspect(connection).get_table_names())
            missing = sorted(CRITICAL_TABLES.difference(tables))
            if missing:
                raise SchemaNotReadyError(f"missing required tables: {', '.join(missing)}")
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
            if revision != EXPECTED_ALEMBIC_HEAD:
                raise SchemaNotReadyError(
                    f"schema revision {revision!r} does not match expected head"
                )

    def dispose(self) -> None:
        """Release connection pool resources during application shutdown."""
        self.engine.dispose()
