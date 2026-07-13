"""Persistence ports for workflow and task aggregates."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol
from uuid import UUID

from vinami.clinical_case.ports.closure import CaseClosureEvidenceRepository
from vinami.clinical_case.ports.repository import ClinicalCaseRepository
from vinami.shared.domain import AggregateRoot
from vinami.shared.events.contracts import EventEnvelope
from vinami.workflow.domain.definition import DueTimer
from vinami.workflow.domain.model import ClinicalTask, ClinicalWorkflow
from vinami.workflow.ports.decisions import (
    ActorAuthorizationRepository,
    PhysicianDecisionRepository,
)


class ClinicalWorkflowRepository(Protocol):
    """Persist versioned physician-review workflow state."""

    def add(self, workflow: ClinicalWorkflow) -> None:
        """Stage a workflow for a clinical case."""

    def get_by_case_id(self, case_id: UUID) -> ClinicalWorkflow | None:
        """Return a case workflow when present."""

    def get(self, workflow_id: UUID) -> ClinicalWorkflow | None:
        """Return a workflow by identifier."""

    def save(self, workflow: ClinicalWorkflow) -> None:
        """Stage a workflow version update."""

    def due_timers(self, now: datetime) -> tuple[tuple[UUID, int, DueTimer], ...]:
        """Return due timers and their expected workflow versions."""


class ClinicalTaskRepository(Protocol):
    """Persist clinical work items and their completion provenance."""

    def add(self, task: ClinicalTask) -> None:
        """Stage a new task."""

    def get(self, task_id: UUID) -> ClinicalTask | None:
        """Return a task by UUID."""

    def save(self, task: ClinicalTask) -> None:
        """Stage completion state for a task."""


class WorkflowUnitOfWork(Protocol):
    """Application-facing transaction boundary for workflow commands."""

    workflows: ClinicalWorkflowRepository
    cases: ClinicalCaseRepository
    closure_evidence: CaseClosureEvidenceRepository
    physician_decisions: PhysicianDecisionRepository
    actors: ActorAuthorizationRepository

    def __enter__(self) -> WorkflowUnitOfWork:
        """Open the transaction boundary."""

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None:
        """Close and roll back uncommitted work when necessary."""

    def collect_events(self, aggregates: Iterable[AggregateRoot]) -> None:
        """Stage aggregate events in the transactional outbox."""

    def stage_event(self, event: EventEnvelope) -> None:
        """Stage an immutable application event in the transactional outbox."""

    def commit(self) -> None:
        """Commit aggregate and outbox changes atomically."""
