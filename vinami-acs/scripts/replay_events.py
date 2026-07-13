"""Replay selected internal outbox event types over an explicit UTC time range."""

from __future__ import annotations

import argparse
from datetime import datetime

from vinami.shared.container import AppContainer
from vinami.shared.events.dispatcher import ReplayRequest


def parse_utc(value: str) -> datetime:
    """Parse an ISO-8601 timestamp and reject values without an explicit timezone."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include an explicit UTC offset")
    return parsed


def arguments() -> argparse.Namespace:
    """Define a deliberate replay interface that requires selection and time bounds."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-type", action="append", required=True)
    parser.add_argument("--start", required=True, type=parse_utc)
    parser.add_argument("--end", required=True, type=parse_utc)
    return parser.parse_args()


def main() -> None:
    """Run one selected replay through the same DI-composed dispatcher as the worker."""
    args = arguments()
    container = AppContainer.create()
    try:
        replayed = container.event_dispatcher().replay(
            ReplayRequest(tuple(args.event_type), args.start, args.end)
        )
        print(f"replayed={replayed}")
    finally:
        container.database.dispose()


if __name__ == "__main__":
    main()
