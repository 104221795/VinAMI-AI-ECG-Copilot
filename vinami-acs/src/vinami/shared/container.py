"""Dependency-injection composition root for technical platform services."""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from vinami.audit.adapters.writer import SQLAlchemyAuditWriter
from vinami.identity.adapters.binding import SQLAlchemyIdentityBinding
from vinami.identity.adapters.development import DevelopmentIdentityProvider
from vinami.identity.adapters.oidc import OIDCIdentityProvider
from vinami.identity.application.authorization import ExplicitAuthorizationPolicy
from vinami.identity.ports.authorization import AuthorizationPolicy
from vinami.identity.ports.provider import IdentityBinding, IdentityProvider
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
    identity_provider: IdentityProvider
    identity_binding: IdentityBinding
    authorization_policy: AuthorizationPolicy

    @classmethod
    def create(cls, settings: Settings | None = None) -> AppContainer:
        """Compose validated settings and infrastructure adapters."""
        configured_settings = settings or Settings()
        if configured_settings.identity_mode is None:
            raise RuntimeError("VINAMI_IDENTITY_MODE must explicitly select development or oidc")
        initialize_mappings()
        database = Database.from_settings(configured_settings)
        return cls(
            settings=configured_settings,
            database=database,
            metrics=Metrics.create(),
            logger=configure_logging(configured_settings),
            identity_provider=_identity_provider(configured_settings),
            identity_binding=SQLAlchemyIdentityBinding(database.session_factory),
            authorization_policy=ExplicitAuthorizationPolicy(),
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


def _identity_provider(settings: Settings) -> IdentityProvider:
    """Build exactly one provider from validated environment-driven configuration."""
    if settings.identity_mode == "development":
        return DevelopmentIdentityProvider()
    assert settings.oidc_issuer is not None
    assert settings.oidc_audience is not None
    assert settings.oidc_jwks_url is not None
    return OIDCIdentityProvider(
        issuer=settings.oidc_issuer,
        audience=settings.oidc_audience,
        jwks_url=settings.oidc_jwks_url,
        allowed_algorithms=settings.oidc_algorithms,
        role_claim=settings.oidc_role_claim,
        permission_claim=settings.oidc_permission_claim,
    )
