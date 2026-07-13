"""Run the internal PostgreSQL outbox dispatcher alongside a Redis connectivity check."""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Callable
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from vinami.shared.config import Settings
from vinami.shared.container import AppContainer
from vinami.shared.logging import log_event
from vinami.workflow.application.commands import WorkflowTimerService
from vinami.workflow.application.definitions import load_demo_workflow_definition
from vinami.workflow.ports.repository import WorkflowUnitOfWork


async def run() -> None:
    """Verify Redis, run due workflow timers, then dispatch durable outbox events."""
    settings = Settings()
    container = AppContainer.create(settings)
    logger = container.logger
    dispatcher = container.event_dispatcher()
    workflow_uow_factory = cast(Callable[[], WorkflowUnitOfWork], container.unit_of_work)
    timer_service = WorkflowTimerService(workflow_uow_factory, load_demo_workflow_definition())
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    stop = asyncio.Event()

    def request_stop() -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_name, request_stop)
    try:
        log_event(logger, "worker_started", role="internal_outbox_dispatcher")
        while not stop.is_set():
            try:
                await client.ping()
                due_timers_processed = timer_service.run_due_timers()
                summary = dispatcher.dispatch_pending()
                if (
                    due_timers_processed
                    or summary.published
                    or summary.retried
                    or summary.dead_lettered
                ):
                    log_event(
                        logger,
                        "worker_cycle_completed",
                        due_timers_processed=due_timers_processed,
                        published=summary.published,
                        retried=summary.retried,
                        dead_lettered=summary.dead_lettered,
                    )
            except (RedisError, SQLAlchemyError) as error:
                log_event(
                    logger,
                    "worker_dependency_unavailable",
                    error_type=type(error).__name__,
                )
            try:
                await asyncio.wait_for(
                    stop.wait(), timeout=settings.event_dispatch_interval_seconds
                )
            except TimeoutError:
                continue
    finally:
        await client.aclose()
        container.database.dispose()
        log_event(logger, "worker_stopped")


def main() -> None:
    """Start the platform worker process."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
