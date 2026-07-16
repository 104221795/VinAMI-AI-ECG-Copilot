"""R6 operational workflow use cases driven only by persisted clinical authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from vinami.alerts.domain.model import Alert, AlertSeverity
from vinami.reasoning.domain.clinical_evidence import ClinicalDecisionType
from vinami.shared.actor import ActorContext
from vinami.shared.application_errors import ResourceConflictError, ResourceNotFoundError
from vinami.shared.domain import DomainInvariantError, require_text, utc_now
from vinami.shared.events.contracts import EventContext, EventEnvelope
from vinami.shared.idempotency import IdempotencyResult, command_fingerprint
from vinami.shared.unit_of_work import SQLAlchemyUnitOfWork
from vinami.workflow.domain.decision import PhysicianDecisionType
from vinami.workflow.domain.model import (
    ClinicalTask,
    TaskAssignment,
    TaskPriority,
    TaskStatus,
)

_TASK_FOR_DECISION = {
    ClinicalDecisionType.REQUEST_REPEAT_ECG: "repeat_ecg",
    ClinicalDecisionType.REQUEST_REPEAT_TROPONIN: "repeat_troponin",
    ClinicalDecisionType.REQUEST_ADDITIONAL_INFORMATION: "obtain_additional_information",
    ClinicalDecisionType.REQUEST_CARDIOLOGY_REVIEW: "cardiology_review",
    ClinicalDecisionType.REQUEST_CATH_LAB_REVIEW: "cath_lab_review",
    ClinicalDecisionType.OTHER_DOCUMENTED_PLAN: "other_documented_task",
}


class UnitOfWorkFactoryProtocol(Protocol):
    """Create one R6 transaction boundary."""

    def __call__(self) -> SQLAlchemyUnitOfWork: ...


@dataclass(frozen=True, slots=True)
class GenerateTaskFromDecision:
    case_id: UUID
    decision_id: UUID
    expected_decision_version: int
    expected_workflow_version: int
    priority: TaskPriority
    due_at: datetime | None
    actor: ActorContext
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ChangeTask:
    case_id: UUID
    task_id: UUID
    expected_version: int
    action: str
    actor: ActorContext
    idempotency_key: str
    owner_user_id: UUID | None = None
    owner_team_id: UUID | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluateOverdueTasks:
    case_id: UUID
    actor: ActorContext
    idempotency_key: str
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ChangeAlert:
    case_id: UUID
    alert_id: UUID
    expected_version: int
    action: str
    actor: ActorContext
    idempotency_key: str
    reason: str | None = None


class WorkflowOperationsService:
    """Apply operational work commands without creating clinical conclusions."""

    def __init__(self, unit_of_work_factory: UnitOfWorkFactoryProtocol) -> None:
        self._uow = unit_of_work_factory

    def generate_task(self, command: GenerateTaskFromDecision) -> dict[str, object]:
        fingerprint = command_fingerprint(
            {
                "case_id": command.case_id,
                "decision_id": command.decision_id,
                "expected_decision_version": command.expected_decision_version,
                "expected_workflow_version": command.expected_workflow_version,
                "priority": command.priority,
                "due_at": command.due_at,
            }
        )
        with self._uow() as uow:
            existing = self._existing(
                uow, command.actor, "generate_workflow_task", command.idempotency_key, fingerprint
            )
            if existing:
                return dict(existing.response_payload)
            workflow = uow.workflows.get_by_case_id(command.case_id)
            if workflow is None:
                raise ResourceNotFoundError("clinical workflow was not found")
            if workflow.version != command.expected_workflow_version:
                raise ResourceConflictError("stale workflow version")
            decision = uow.reasoning.get_decision(command.decision_id)
            if decision is None or decision.clinical_case_id != command.case_id:
                raise ResourceNotFoundError("physician decision was not found for this case")
            if decision.record_version != command.expected_decision_version:
                raise ResourceConflictError("stale physician decision version")
            if not uow.reasoning.is_decision_effective(decision.decision_id):
                raise ResourceConflictError("revoked physician decision cannot authorize a task")
            task_type = _TASK_FOR_DECISION.get(decision.decision_type)
            if task_type is None:
                raise ResourceConflictError(
                    "this physician decision does not request operational work"
                )
            if decision.decision_type is ClinicalDecisionType.REQUEST_CATH_LAB_REVIEW:
                self._require_cath_authorization(
                    uow, command.case_id, decision.workflow_authorization_id
                )
            duplicate = uow.tasks.find_by_source(
                command.case_id, "physician_decision", decision.decision_id
            )
            if duplicate is not None:
                response = _task_dict(duplicate)
            else:
                task = ClinicalTask.create(
                    command.case_id,
                    task_type,
                    workflow_id=workflow.id,
                    originating_decision_id=decision.decision_id,
                    source_type="physician_decision",
                    source_id=decision.decision_id,
                    priority=command.priority,
                    due_at=command.due_at,
                    created_by=command.actor.actor_id,
                )
                uow.tasks.add(task)
                response = _task_dict(task)
                self._event(
                    uow,
                    "ClinicalTaskCreated.v1",
                    task.id,
                    task.version,
                    command.case_id,
                    command.actor,
                    response,
                )
            self._store(
                uow,
                command.actor,
                "generate_workflow_task",
                command.idempotency_key,
                fingerprint,
                UUID(str(response["task_id"])),
                response,
            )
            uow.commit()
            return response

    def change_task(self, command: ChangeTask) -> dict[str, object]:
        fingerprint = command_fingerprint(
            command.__dict__
            if hasattr(command, "__dict__")
            else {
                "case_id": command.case_id,
                "task_id": command.task_id,
                "expected_version": command.expected_version,
                "action": command.action,
                "owner_user_id": command.owner_user_id,
                "owner_team_id": command.owner_team_id,
                "reason": command.reason,
            }
        )
        command_type = f"workflow_task_{command.action}"
        with self._uow() as uow:
            existing = self._existing(
                uow, command.actor, command_type, command.idempotency_key, fingerprint
            )
            if existing:
                return dict(existing.response_payload)
            task = uow.tasks.get(command.task_id)
            if task is None or task.case_id != command.case_id:
                raise ResourceNotFoundError("clinical task was not found for this case")
            if task.version != command.expected_version:
                raise ResourceConflictError("stale clinical task version")
            now = utc_now()
            try:
                if command.action == "assign":
                    task.assign(
                        TaskAssignment(command.owner_team_id, command.owner_user_id, now),
                        command.actor.actor_id,
                    )
                elif command.action == "acknowledge":
                    task.acknowledge(command.actor.actor_id, now)
                elif command.action == "start":
                    task.start_work(command.actor.actor_id, now)
                elif command.action == "complete":
                    if command.reason is None:
                        raise ResourceConflictError("completion reason is required")
                    task.complete(
                        command.actor.actor_id,
                        require_text(command.reason, "completion reason"),
                        now,
                    )
                elif command.action == "cancel":
                    if command.reason is None:
                        raise ResourceConflictError("cancellation reason is required")
                    task.cancel(
                        command.actor.actor_id,
                        require_text(command.reason, "cancellation reason"),
                        now,
                    )
                else:
                    raise ResourceConflictError("unsupported task action")
            except DomainInvariantError as error:
                raise ResourceConflictError(str(error)) from error
            uow.tasks.save(task)
            response = _task_dict(task)
            self._event(
                uow,
                "ClinicalTaskTransitioned.v1",
                task.id,
                task.version,
                command.case_id,
                command.actor,
                {
                    "task_id": str(task.id),
                    "action": command.action,
                    "status": task.status.value,
                    "reason": command.reason,
                },
            )
            terminal_event = {
                "complete": "ClinicalTaskCompleted.v1",
                "cancel": "ClinicalTaskCancelled.v1",
            }.get(command.action)
            if terminal_event is not None:
                self._event(
                    uow,
                    terminal_event,
                    task.id,
                    task.version,
                    command.case_id,
                    command.actor,
                    {
                        "task_id": str(task.id),
                        "status": task.status.value,
                        "reason": command.reason,
                    },
                )
            self._store(
                uow,
                command.actor,
                command_type,
                command.idempotency_key,
                fingerprint,
                task.id,
                response,
            )
            uow.commit()
            return response

    def evaluate_overdue(self, command: EvaluateOverdueTasks) -> dict[str, object]:
        evaluated_at = command.evaluated_at or utc_now()
        fingerprint = command_fingerprint(
            {"case_id": command.case_id, "evaluated_at": evaluated_at}
        )
        with self._uow() as uow:
            existing = self._existing(
                uow, command.actor, "evaluate_overdue_tasks", command.idempotency_key, fingerprint
            )
            if existing:
                return dict(existing.response_payload)
            if uow.cases.get(command.case_id) is None:
                raise ResourceNotFoundError("clinical case was not found")
            changed: list[str] = []
            for task in uow.tasks.list_by_case(command.case_id):
                if (
                    task.due_at is None
                    or task.due_at > evaluated_at
                    or task.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}
                ):
                    continue
                if task.status is not TaskStatus.OVERDUE:
                    task.mark_overdue(command.actor.actor_id, evaluated_at)
                elif task.escalation_level == 0:
                    task.escalate(command.actor.actor_id, evaluated_at)
                uow.tasks.save(task)
                self._ensure_overdue_alert(uow, task, command.actor, evaluated_at)
                changed.append(str(task.id))
                self._event(
                    uow,
                    "ClinicalTaskOverdue.v1",
                    task.id,
                    task.version,
                    command.case_id,
                    command.actor,
                    {"task_id": str(task.id), "due_at": task.due_at, "status": task.status.value},
                )
            response: dict[str, object] = {
                "case_id": str(command.case_id),
                "evaluated_at": evaluated_at.isoformat(),
                "changed_task_ids": changed,
            }
            self._store(
                uow,
                command.actor,
                "evaluate_overdue_tasks",
                command.idempotency_key,
                fingerprint,
                command.case_id,
                response,
            )
            uow.commit()
            return response

    def change_alert(self, command: ChangeAlert) -> dict[str, object]:
        fingerprint = command_fingerprint(
            {
                "case_id": command.case_id,
                "alert_id": command.alert_id,
                "expected_version": command.expected_version,
                "action": command.action,
                "reason": command.reason,
            }
        )
        command_type = f"workflow_alert_{command.action}"
        with self._uow() as uow:
            existing = self._existing(
                uow, command.actor, command_type, command.idempotency_key, fingerprint
            )
            if existing:
                return dict(existing.response_payload)
            alert = uow.alerts.get(command.alert_id)
            if alert is None or alert.case_id != command.case_id:
                raise ResourceNotFoundError("clinical alert was not found for this case")
            if alert.version != command.expected_version:
                raise ResourceConflictError("stale clinical alert version")
            try:
                if command.action == "acknowledge":
                    alert.acknowledge(command.actor.actor_id)
                elif command.action == "resolve":
                    if command.reason is None:
                        raise ResourceConflictError("resolution reason is required")
                    alert.resolve(
                        command.actor.actor_id, require_text(command.reason, "resolution reason")
                    )
                else:
                    raise ResourceConflictError("unsupported alert action")
            except DomainInvariantError as error:
                raise ResourceConflictError(str(error)) from error
            uow.alerts.save(alert)
            response = _alert_dict(alert)
            event_type = (
                "ClinicalAlertAcknowledged.v1"
                if command.action == "acknowledge"
                else "ClinicalAlertResolved.v1"
            )
            self._event(
                uow,
                event_type,
                alert.id,
                alert.version,
                command.case_id,
                command.actor,
                {"alert_id": str(alert.id), "status": alert.status.value, "reason": command.reason},
            )
            self._store(
                uow,
                command.actor,
                command_type,
                command.idempotency_key,
                fingerprint,
                alert.id,
                response,
            )
            uow.commit()
            return response

    @staticmethod
    def _require_cath_authorization(
        uow: SQLAlchemyUnitOfWork, case_id: UUID, authorization_id: UUID | None
    ) -> None:
        if authorization_id is None:
            raise ResourceConflictError("cath-lab task requires R0 physician authorization")
        authorization = uow.physician_decisions.get(authorization_id)
        if authorization is None or authorization.clinical_case_id != case_id:
            raise ResourceConflictError("cath-lab authorization does not belong to this case")
        if (
            authorization.decision_type is not PhysicianDecisionType.CATH_LAB_REVIEW_REQUESTED
            or not uow.physician_decisions.is_effective(authorization_id)
        ):
            raise ResourceConflictError("cath-lab physician authorization is not effective")

    def _ensure_overdue_alert(
        self, uow: SQLAlchemyUnitOfWork, task: ClinicalTask, actor: ActorContext, at: datetime
    ) -> None:
        key = f"task-overdue:{task.id}"
        alert = uow.alerts.get_by_deduplication_key(key)
        if alert is None:
            alert = Alert.raise_alert(
                task.case_id,
                "task_overdue",
                "workflow_operations",
                AlertSeverity.URGENT,
                "A time-bound clinical task is overdue and requires human review.",
                at,
                workflow_id=task.workflow_id,
                task_id=task.id,
                deduplication_key=key,
            )
            uow.alerts.add(alert)
            self._event(
                uow,
                "ClinicalAlertRaised.v1",
                alert.id,
                alert.version,
                task.case_id,
                actor,
                {
                    "alert_id": str(alert.id),
                    "task_id": str(task.id),
                    "severity": alert.severity.value,
                    "reason": "task_overdue",
                },
            )
        elif task.escalation_level > alert.escalation_level:
            alert.escalate(actor.actor_id)
            uow.alerts.save(alert)
            self._event(
                uow,
                "ClinicalAlertEscalated.v1",
                alert.id,
                alert.version,
                task.case_id,
                actor,
                {
                    "alert_id": str(alert.id),
                    "task_id": str(task.id),
                    "escalation_level": alert.escalation_level,
                },
            )

    @staticmethod
    def _existing(
        uow: SQLAlchemyUnitOfWork,
        actor: ActorContext,
        command_type: str,
        key: str,
        fingerprint: str,
    ) -> IdempotencyResult | None:
        existing = uow.idempotency.lock_and_get(
            actor.actor_id, command_type, require_text(key, "idempotency_key")
        )
        if existing and existing.request_hash != fingerprint:
            raise ResourceConflictError("idempotency key was already used with a different request")
        return existing

    @staticmethod
    def _store(
        uow: SQLAlchemyUnitOfWork,
        actor: ActorContext,
        command_type: str,
        key: str,
        fingerprint: str,
        resource_id: UUID,
        response: dict[str, object],
    ) -> None:
        uow.idempotency.add(
            IdempotencyResult(
                actor.actor_id,
                command_type,
                key,
                uuid4(),
                fingerprint,
                "WorkflowOperations",
                resource_id,
                response,
                utc_now(),
            )
        )

    @staticmethod
    def _event(
        uow: SQLAlchemyUnitOfWork,
        event_type: str,
        aggregate_id: UUID,
        version: int,
        case_id: UUID,
        actor: ActorContext,
        payload: dict[str, Any],
    ) -> None:
        uow.stage_event(
            EventEnvelope.from_context(
                event_type=event_type,
                aggregate_type="ClinicalWorkflowOperation",
                aggregate_id=aggregate_id,
                aggregate_version=version,
                payload={"case_id": str(case_id), **payload},
                context=EventContext(
                    actor.correlation_id, actor.causation_id, actor.actor_id, actor.audit_metadata()
                ),
            )
        )


class WorkflowOperationsQueryService:
    """Return the authoritative R6 case workflow workspace."""

    def __init__(self, unit_of_work_factory: UnitOfWorkFactoryProtocol) -> None:
        self._uow = unit_of_work_factory

    def workspace(self, case_id: UUID) -> dict[str, object]:
        with self._uow() as uow:
            case = uow.cases.get(case_id)
            if case is None:
                raise ResourceNotFoundError("clinical case was not found")
            workflow = uow.workflows.get_by_case_id(case_id)
            if workflow is None:
                raise ResourceNotFoundError("clinical workflow was not found")
            tasks = uow.tasks.list_by_case(case_id)
            decisions = {item.decision_id: item for item in uow.reasoning.decisions(case_id)}
            return {
                "case_id": str(case_id),
                "case_version": case.version,
                "workflow": {
                    "workflow_id": str(workflow.id),
                    "state": workflow.state.value,
                    "version": workflow.version,
                    "definition_version": workflow.definition_version,
                    "demonstration_notice": workflow.demonstration_notice,
                },
                "tasks": [
                    _task_dict(task)
                    | {
                        "originating_decision": _decision_summary(
                            decisions.get(task.originating_decision_id)
                            if task.originating_decision_id is not None
                            else None
                        )
                    }
                    for task in tasks
                ],
                "alerts": [_alert_dict(alert) for alert in uow.alerts.list_by_case(case_id)],
                "safety_notice": (
                    "Operational workflow only. Task completion does not imply diagnosis, "
                    "treatment success, or case closure."
                ),
            }


def _task_dict(task: ClinicalTask) -> dict[str, object]:
    return {
        "task_id": str(task.id),
        "case_id": str(task.case_id),
        "workflow_id": str(task.workflow_id) if task.workflow_id else None,
        "task_type": task.task_type,
        "status": task.status.value,
        "priority": task.priority.value,
        "version": task.version,
        "created_at": task.created_at.isoformat(),
        "created_by": str(task.created_by) if task.created_by else None,
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "originating_decision_id": str(task.originating_decision_id)
        if task.originating_decision_id
        else None,
        "source_type": task.source_type,
        "source_id": str(task.source_id) if task.source_id else None,
        "owner_user_id": str(task.assignment.user_id)
        if task.assignment and task.assignment.user_id
        else None,
        "owner_team_id": str(task.assignment.team_id)
        if task.assignment and task.assignment.team_id
        else None,
        "acknowledged_at": task.acknowledged_at.isoformat() if task.acknowledged_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "outcome": task.outcome,
        "cancelled_at": task.cancelled_at.isoformat() if task.cancelled_at else None,
        "cancellation_reason": task.cancellation_reason,
        "overdue_at": task.overdue_at.isoformat() if task.overdue_at else None,
        "escalation_level": task.escalation_level,
        "history": [
            {
                "transition_id": str(item.transition_id),
                "from_status": item.from_status.value,
                "to_status": item.to_status.value,
                "actor_id": str(item.actor_id),
                "occurred_at": item.occurred_at.isoformat(),
                "reason": item.reason,
            }
            for item in task.transition_history
        ],
    }


def _alert_dict(alert: Alert) -> dict[str, object]:
    return {
        "alert_id": str(alert.id),
        "case_id": str(alert.case_id),
        "workflow_id": str(alert.workflow_id) if alert.workflow_id else None,
        "task_id": str(alert.task_id) if alert.task_id else None,
        "alert_type": alert.alert_type,
        "source": alert.source,
        "severity": alert.severity.value,
        "message": alert.message,
        "status": alert.status.value,
        "version": alert.version,
        "raised_at": alert.raised_at.isoformat(),
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "resolution_reason": alert.resolution_reason,
        "escalation_level": alert.escalation_level,
        "history": [
            {
                "transition_id": str(item.transition_id),
                "from_status": item.from_status.value,
                "to_status": item.to_status.value,
                "actor_id": str(item.actor_id),
                "occurred_at": item.occurred_at.isoformat(),
                "reason": item.reason,
            }
            for item in alert.transitions
        ],
    }


def _decision_summary(decision: Any) -> dict[str, object] | None:
    if decision is None:
        return None
    return {
        "decision_id": str(decision.decision_id),
        "decision_type": decision.decision_type.value,
        "status": decision.status.value,
        "recorded_at": decision.recorded_at.isoformat(),
        "rationale": decision.rationale,
    }
