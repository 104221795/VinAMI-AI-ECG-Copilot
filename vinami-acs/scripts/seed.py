"""Validate deterministic platform seed prerequisites without creating clinical records."""

from __future__ import annotations

from vinami.shared.config import Settings
from vinami.shared.database import Database
from vinami.shared.logging import configure_logging, log_event


def main() -> None:
    """Probe the system-of-record before later sprints add approved seed fixtures."""
    settings = Settings()
    logger = configure_logging(settings)
    database = Database.from_settings(settings)
    try:
        database.probe()
        log_event(logger, "seed_platform_verified", clinical_records_created=0)
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
