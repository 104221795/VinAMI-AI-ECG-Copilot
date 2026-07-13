"""Migration upgrade/downgrade verification against disposable PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_initial_migration_downgrades_and_upgrades(postgres_session_factory: object) -> None:
    """The initial schema can revert to base and return to all required tables."""
    _ = postgres_session_factory
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)
    engine = create_engine(os.environ["VINAMI_DATABASE_URL"])
    try:
        tables = set(inspect(engine).get_table_names())
        assert {
            "patients",
            "clinical_cases",
            "outbox_events",
            "event_consumptions",
            "workflow_transition_history",
            "workflow_due_timers",
            "workflow_command_receipts",
            "physician_decisions",
            "command_idempotency",
            "ecg_studies",
            "lab_results",
        } <= tables
    finally:
        engine.dispose()
