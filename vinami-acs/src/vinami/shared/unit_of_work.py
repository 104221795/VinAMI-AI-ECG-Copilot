"""Explicit SQLAlchemy unit of work with transactional outbox staging."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from vinami.alerts.adapters.persistence import SQLAlchemyAlertRepository
from vinami.audit.adapters.history import SQLAlchemyCaseHistoryRepository
from vinami.audit.adapters.persistence import OutboxEventRecord
from vinami.clinical_case.adapters.case_workspace import SQLAlchemyCaseWorkspaceReadRepository
from vinami.clinical_case.adapters.closure import SQLAlchemyCaseClosureEvidenceRepository
from vinami.clinical_case.adapters.command_center import (
    SQLAlchemyCommandCenterReadRepository,
)
from vinami.clinical_case.adapters.persistence import SQLAlchemyClinicalCaseRepository
from vinami.clinical_case.adapters.read_models import (
    SQLAlchemyClinicalLifecycleReadRepository,
)
from vinami.ecg.adapters.persistence import SQLAlchemyECGStudyRepository
from vinami.ecg.adapters.r3_persistence import SQLAlchemyECGClinicalRepository
from vinami.identity.adapters.authorization import SQLAlchemyActorAuthorizationRepository
from vinami.integration.adapters.persistence import SQLAlchemyIntegrationMessageRepository
from vinami.model_registry.adapters.persistence import SQLAlchemyModelRegistryRepository
from vinami.patient.adapters.persistence import (
    SQLAlchemyEncounterRepository,
    SQLAlchemyPatientRepository,
)
from vinami.reasoning.adapters.r5_persistence import SQLAlchemyClinicalReasoningRepository
from vinami.shared.domain import AggregateRoot, OptimisticConcurrencyError
from vinami.shared.events.contracts import EventEnvelope
from vinami.shared.idempotency_persistence import SQLAlchemyIdempotencyRepository
from vinami.triage.adapters.persistence import SQLAlchemyClinicalDocumentationRepository
from vinami.troponin.adapters.persistence import SQLAlchemyTroponinTimelineRepository
from vinami.troponin.adapters.r4_persistence import SQLAlchemyTroponinEvidenceRepository
from vinami.workflow.adapters.decision_persistence import (
    SQLAlchemyPhysicianDecisionRepository,
)
from vinami.workflow.adapters.persistence import (
    SQLAlchemyClinicalTaskRepository,
    SQLAlchemyClinicalWorkflowRepository,
)


def _json_value(value: Any) -> Any:
    """Convert UUID and timestamp payload leaves into JSON-compatible strings."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return str(value) if type(value).__name__ == "UUID" else value


class SQLAlchemyUnitOfWork:
    """Own one explicit transaction, repositories, and its transactional outbox rows."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Receive a session factory from the infrastructure composition root."""
        self._session_factory = session_factory
        self._session: Session | None = None
        self._aggregates: list[AggregateRoot] = []
        self._events: list[EventEnvelope] = []

    def __enter__(self) -> SQLAlchemyUnitOfWork:
        """Open a unit of work and construct repositories bound to its transaction."""
        self._session = self._session_factory()
        self.patients = SQLAlchemyPatientRepository(self._session)
        self.encounters = SQLAlchemyEncounterRepository(self._session)
        self.cases = SQLAlchemyClinicalCaseRepository(self._session)
        self.case_workspace = SQLAlchemyCaseWorkspaceReadRepository(self._session)
        self.command_center = SQLAlchemyCommandCenterReadRepository(self._session)
        self.lifecycle_reads = SQLAlchemyClinicalLifecycleReadRepository(self._session)
        self.closure_evidence = SQLAlchemyCaseClosureEvidenceRepository(self._session)
        self.ecg_studies = SQLAlchemyECGStudyRepository(self._session)
        self.ecg_clinical = SQLAlchemyECGClinicalRepository(self._session)
        self.troponin_timelines = SQLAlchemyTroponinTimelineRepository(self._session)
        self.troponin_evidence = SQLAlchemyTroponinEvidenceRepository(self._session)
        self.documentation = SQLAlchemyClinicalDocumentationRepository(self._session)
        self.reasoning = SQLAlchemyClinicalReasoningRepository(self._session)
        self.workflows = SQLAlchemyClinicalWorkflowRepository(self._session)
        self.tasks = SQLAlchemyClinicalTaskRepository(self._session)
        self.alerts = SQLAlchemyAlertRepository(self._session)
        self.history = SQLAlchemyCaseHistoryRepository(self._session)
        self.integration_messages = SQLAlchemyIntegrationMessageRepository(self._session)
        self.models = SQLAlchemyModelRegistryRepository(self._session)
        self.physician_decisions = SQLAlchemyPhysicianDecisionRepository(self._session)
        self.actors = SQLAlchemyActorAuthorizationRepository(self._session)
        self.idempotency = SQLAlchemyIdempotencyRepository(self._session)
        return self

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None:
        """Roll back uncommitted work and always release the database session."""
        if self._session is None:
            return
        if self._session.in_transaction():
            self._session.rollback()
        self._session.close()
        self._session = None

    def collect_events(self, aggregates: Iterable[AggregateRoot]) -> None:
        """Register aggregates whose pending events must be staged with this transaction."""
        self._aggregates.extend(aggregates)

    def stage_event(self, event: EventEnvelope) -> None:
        """Stage an application event that is not owned by a mutable aggregate."""
        self._events.append(event)

    def commit(self) -> None:
        """Flush repositories and outbox events atomically, translating stale writes explicitly."""
        session = self._require_session()
        for aggregate in self._aggregates:
            for event in aggregate.pull_events():
                session.add(self._outbox_record(event))
        for event in self._events:
            session.add(self._outbox_record(event))
        try:
            session.commit()
        except StaleDataError as error:
            session.rollback()
            raise OptimisticConcurrencyError("concurrent persistence update detected") from error
        finally:
            self._aggregates.clear()
            self._events.clear()

    def rollback(self) -> None:
        """Explicitly discard all uncommitted records and unstaged repository changes."""
        self._require_session().rollback()
        self._aggregates.clear()
        self._events.clear()

    def _require_session(self) -> Session:
        if self._session is None:
            raise RuntimeError("unit of work must be entered before use")
        return self._session

    @staticmethod
    def _outbox_record(event: EventEnvelope) -> OutboxEventRecord:
        """Map a normalized domain event to the durable outbox contract."""
        return OutboxEventRecord(
            event_id=event.event_id,
            event_type=event.event_type,
            event_version=event.event_version,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            aggregate_version=event.aggregate_version,
            occurred_at=event.occurred_at,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            actor_id=event.actor_id,
            payload=_json_value(event.payload),
            metadata_document=_json_value(event.metadata),
            available_at=event.occurred_at,
        )
