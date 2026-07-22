"""Focused tests for R13/R14/R17/R21 workflow automation policies."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from vinami.clinical_case.application.automation import (
    AUTOMATION_POLICY_VERSION,
    build_case_automation,
    summarize_alert_digest,
)
from vinami.integration.application.reconciliation import classify_reconciliation
from vinami.integration.domain.model import IntegrationMessage


NOW = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)
CASE_ID = UUID("30000000-0000-4000-8000-000000000013")


def test_r13_completeness_marks_unknown_as_incomplete_not_negative() -> None:
    automation = build_case_automation(
        case_id=CASE_ID,
        now=NOW,
        triage={
            "chief_complaint": "Chest discomfort",
            "symptom_onset_state": "unknown",
            "observations": [
                {
                    "category": "cardiovascular_risk_factor",
                    "name": "smoking history",
                    "state": "unknown",
                }
            ],
        },
        vitals={"measurements": [1]},
        ecg=None,
        troponin={"result_count": 0},
        evidence_freshness={},
        missing_evidence=(),
        stale_evidence=(),
        technical_limits=(),
        tasks=(),
        alerts=(),
    )

    completeness = automation["completeness"]
    assert isinstance(completeness, dict)
    assert completeness["status"] == "incomplete"
    assert completeness["score"] < 100
    assert {"symptom_onset", "risk_factors", "ecg", "troponin"} <= set(
        completeness["missing_evidence"]
    )
    assert "not negative evidence" in str(completeness["not_negative_evidence_notice"])


def test_r14_suggests_due_work_without_duplicating_active_tasks() -> None:
    automation = build_case_automation(
        case_id=CASE_ID,
        now=NOW,
        triage=None,
        vitals=None,
        ecg=None,
        troponin={"result_count": 0},
        evidence_freshness={},
        missing_evidence=("triage", "vitals", "ecg", "troponin"),
        stale_evidence=(),
        technical_limits=(),
        tasks=(
            {
                "task_id": str(uuid4()),
                "task_type": "repeat_ecg",
                "status": "pending",
            },
        ),
        alerts=(),
    )

    suggestions = automation["suggested_tasks"]
    assert isinstance(suggestions, tuple)
    task_types = {item["task_type"] for item in suggestions}
    assert "repeat_ecg" not in task_types
    assert {"repeat_troponin", "obtain_additional_information"} <= task_types
    assert all(item["requires_confirmation"] is True for item in suggestions)
    assert all(item["policy_version"] == AUTOMATION_POLICY_VERSION for item in suggestions)


def test_r21_alert_digest_groups_without_suppressing_urgent_alerts() -> None:
    digest = summarize_alert_digest(
        (
            {
                "alert_id": str(uuid4()),
                "alert_type": "task_overdue",
                "source": "workflow_operations",
                "severity": "urgent",
                "status": "active",
                "raised_at": NOW,
                "message": "Task overdue.",
                "escalation_level": 1,
            },
            {
                "alert_id": str(uuid4()),
                "alert_type": "task_overdue",
                "source": "workflow_operations",
                "severity": "urgent",
                "status": "active",
                "raised_at": NOW,
                "message": "Task overdue.",
                "escalation_level": 0,
            },
        )
    )

    assert len(digest) == 1
    group = digest[0]
    assert group["count"] == 2
    assert group["critical_preserved"] is True
    assert group["max_escalation_level"] == 1


def test_r17_reconciliation_classifies_matched_out_of_order_and_review_required() -> None:
    matched = _message(status="processed", linked_record_ids=("record-1",))
    out_of_order = _message(
        status="dead_letter",
        message_type="lab_result_amendment",
        validation_errors=("amendment predecessor has not been processed",),
    )
    unmatched = _message(status="failed", clinical_case_id=None)

    assert classify_reconciliation(matched)["reconciliation_status"] == "matched"
    assert classify_reconciliation(out_of_order)["reconciliation_status"] == "out_of_order"
    assert classify_reconciliation(out_of_order)["review_required"] is True
    assert classify_reconciliation(unmatched)["reconciliation_status"] == "unmatched"


def _message(
    *,
    status: str,
    message_type: str = "lab_result",
    clinical_case_id: UUID | None = CASE_ID,
    validation_errors: tuple[str, ...] = (),
    linked_record_ids: tuple[str, ...] = (),
) -> IntegrationMessage:
    return IntegrationMessage(
        message_id=uuid4(),
        external_message_id=f"MSG-{uuid4()}",
        source_system="simulated-lis",
        message_type=message_type,
        schema_version="vinami-hl7-lab-result.v1",
        clinical_case_id=clinical_case_id,
        received_at=NOW,
        processed_at=NOW if status != "received" else None,
        status=status,
        correlation_id=uuid4(),
        causation_id=None,
        retry_count=1 if status in {"failed", "dead_letter"} else 0,
        validation_errors=validation_errors,
        linked_record_ids=linked_record_ids,
        payload={},
        dead_letter_reason="synthetic failure" if status == "dead_letter" else None,
        simulated=True,
        record_version=1,
    )
