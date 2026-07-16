"""Focused R6 task and alert lifecycle invariants."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from vinami.alerts.domain.model import Alert, AlertSeverity, AlertStatus
from vinami.shared.domain import DomainInvariantError
from vinami.workflow.domain.model import (
    ClinicalTask,
    TaskAssignment,
    TaskPriority,
    TaskStatus,
)

NOW = datetime(2026, 7, 15, 8, 0, tzinfo=UTC)


def test_task_requires_valid_ordered_transitions_and_reasons() -> None:
    actor_id = uuid4()
    task = ClinicalTask.create(
        uuid4(),
        "repeat_ecg",
        created_at=NOW,
        source_type="physician_decision",
        source_id=uuid4(),
        priority=TaskPriority.URGENT,
        due_at=NOW + timedelta(minutes=15),
        created_by=actor_id,
    )
    assert task.status is TaskStatus.PENDING
    with pytest.raises(DomainInvariantError, match="assigned task"):
        task.acknowledge(actor_id, NOW)
    task.assign(TaskAssignment(None, actor_id, NOW), actor_id)
    task.acknowledge(actor_id, NOW)
    task.start_work(actor_id, NOW)
    task.complete(actor_id, "Repeat ECG acquisition documented.", NOW)
    assert task.status is TaskStatus.COMPLETED
    assert task.version == 5
    assert [item.to_status for item in task.transition_history] == [
        TaskStatus.ASSIGNED,
        TaskStatus.ACKNOWLEDGED,
        TaskStatus.IN_PROGRESS,
        TaskStatus.COMPLETED,
    ]
    with pytest.raises(DomainInvariantError, match="cannot be cancelled"):
        task.cancel(actor_id, "Not applicable", NOW)


def test_overdue_and_alert_history_are_authoritative_and_append_only() -> None:
    actor_id = uuid4()
    task = ClinicalTask.create(
        uuid4(),
        "repeat_troponin",
        created_at=NOW,
        source_type="physician_decision",
        source_id=uuid4(),
        due_at=NOW + timedelta(minutes=5),
    )
    with pytest.raises(DomainInvariantError, match="not due"):
        task.mark_overdue(actor_id, NOW)
    task.mark_overdue(actor_id, NOW + timedelta(minutes=6))
    task.escalate(actor_id, NOW + timedelta(minutes=7))
    assert task.status is TaskStatus.OVERDUE
    assert task.escalation_level == 1

    alert = Alert.raise_alert(
        task.case_id,
        "task_overdue",
        "workflow_operations",
        AlertSeverity.URGENT,
        "Human review required.",
        NOW,
        task_id=task.id,
        deduplication_key=f"task-overdue:{task.id}",
    )
    alert.acknowledge(actor_id, NOW)
    alert.resolve(actor_id, "Operational condition reviewed.", NOW)
    assert alert.status is AlertStatus.RESOLVED
    assert len(alert.transitions) == 2
