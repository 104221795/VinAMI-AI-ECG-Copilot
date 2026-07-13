"""Dependency-injection composition root for technical platform services."""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from vinami.audit.adapters.writer import SQLAlchemyAuditWriter
from vinami.shared.config import Settings
from vinami.shared.database import Database
from vinami.shared.events.dispatcher import InternalEventDispatcher
from vinami.shared.events.handlers import build_default_handler_registry
from vinami.shared.events.registry import EventRegistry
from vinami.shared.events.serializer import EventSerializer
from vinami.shared.logging import configure_logging
from vinami.shared.metrics import Metrics
from vinami.shared.orm_registry import initialize_mappings
from vinami.shared.unit_of_work import SQLAlchemyUnitOfWork


@dataclass(slots=True)
class AppContainer:
    """Own dependencies for a single application instance without global state."""

    settings: Settings
    database: Database
    metrics: Metrics
    logger: structlog.stdlib.BoundLogger

    @classmethod
    def create(cls, settings: Settings | None = None) -> AppContainer:
        """Compose validated settings and infrastructure adapters."""
        configured_settings = settings or Settings()
        initialize_mappings()
        return cls(
            settings=configured_settings,
            database=Database.from_settings(configured_settings),
            metrics=Metrics.create(),
            logger=configure_logging(configured_settings),
        )

    def unit_of_work(self) -> SQLAlchemyUnitOfWork:
        """Create an explicit persistence boundary for an application command."""
        return SQLAlchemyUnitOfWork(self.database.session_factory)

    def event_dispatcher(self) -> InternalEventDispatcher:
        """Compose the replaceable PostgreSQL outbox dispatcher and its initial handlers."""
        registry = EventRegistry.default()
        return InternalEventDispatcher(
            session_factory=self.database.session_factory,
            serializer=EventSerializer(registry),
            handlers=build_default_handler_registry(),
            logger=self.logger,
            max_retries=self.settings.event_max_retries,
            retry_delay_seconds=self.settings.event_retry_delay_seconds,
            claim_ttl_seconds=self.settings.event_claim_ttl_seconds,
        )

    def audit_writer(self) -> SQLAlchemyAuditWriter:
        """Create the append-only command audit adapter used by consequential handlers."""
        return SQLAlchemyAuditWriter(self.database.session_factory)
