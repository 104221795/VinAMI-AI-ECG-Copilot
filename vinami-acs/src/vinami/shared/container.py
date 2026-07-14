"""Dependency-injection composition root for technical platform services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import structlog

from vinami.audit.adapters.writer import SQLAlchemyAuditWriter
from vinami.ecg.adapters.artifact_store import LocalECGArtifactStore
from vinami.ecg.adapters.ingestion import (
    CanonicalWaveformAdapter,
    CanonicalXMLAdapter,
    DICOMWaveformAdapter,
    MockDICOMSourceConnector,
    PDFECGAdapter,
)
from vinami.ecg.adapters.mock_provider import MockECGAIProvider
from vinami.ecg.adapters.preprocessing import CanonicalECGPreprocessor, TechnicalECGQualityEngine
from vinami.ecg.adapters.torch_provider import TorchConvNeXtV2Provider
from vinami.ecg.application.service import (
    ECGApplicationService,
    ECGQueryService,
)
from vinami.ecg.application.service import (
    UnitOfWorkFactory as ECGUnitOfWorkFactory,
)
from vinami.ecg.ports.ingestion import ECGSourceAdapter
from vinami.ecg.ports.provider import ECGAIProvider
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

    def ecg_artifact_store(self) -> LocalECGArtifactStore:
        return LocalECGArtifactStore(
            self.settings.ecg_artifact_root,
            self.settings.ecg_artifact_max_bytes,
        )

    def ecg_providers(self) -> dict[str, ECGAIProvider]:
        providers: dict[str, ECGAIProvider] = {}
        if self.settings.ecg_allow_mock_provider:
            providers["mock"] = MockECGAIProvider()
        if self.settings.ecg_checkpoint_path and self.settings.ecg_checkpoint_sha256:
            providers["torch"] = TorchConvNeXtV2Provider(
                self.settings.ecg_checkpoint_path,
                self.settings.ecg_checkpoint_sha256,
                self.settings.ecg_device,
            )
        return providers

    def ecg_application(self) -> ECGApplicationService:
        sources = _ecg_sources()
        return ECGApplicationService(
            cast(ECGUnitOfWorkFactory, self.unit_of_work),
            self.ecg_artifact_store(),
            sources,
            CanonicalECGPreprocessor(),
            TechnicalECGQualityEngine(),
            self.ecg_providers(),
            MockDICOMSourceConnector(),
        )

    def ecg_queries(self) -> ECGQueryService:
        return ECGQueryService(
            cast(ECGUnitOfWorkFactory, self.unit_of_work),
            self.ecg_artifact_store(),
            _ecg_sources(),
            self.ecg_providers(),
            MockDICOMSourceConnector(),
        )


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


def _ecg_sources() -> dict[str, ECGSourceAdapter]:
    adapters = (
        CanonicalWaveformAdapter(),
        DICOMWaveformAdapter(),
        CanonicalXMLAdapter(),
        PDFECGAdapter(),
    )
    return {adapter.source_type: adapter for adapter in adapters}
