"""Focused domain safety tests for immutable R5 physician records."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from vinami.reasoning.domain.clinical_evidence import (
    ClinicalDecisionType,
    DecisionRecordStatus,
    PhysicianClinicalAssessment,
    PhysicianDecision,
)
from vinami.shared.domain import DomainInvariantError

NOW = datetime(2026, 7, 15, 8, 0, tzinfo=UTC)


def test_assessment_requires_physician_and_correction_provenance() -> None:
    with pytest.raises(DomainInvariantError, match="authorized physician"):
        PhysicianClinicalAssessment(
            uuid4(),
            uuid4(),
            uuid4(),
            1,
            1,
            "Summary",
            (),
            (),
            "Uncertain",
            None,
            uuid4(),
            "nurse",
            NOW,
        )
    with pytest.raises(DomainInvariantError, match="source and reason together"):
        PhysicianClinicalAssessment(
            uuid4(),
            uuid4(),
            uuid4(),
            2,
            1,
            "Correction",
            (),
            (),
            "Uncertain",
            None,
            uuid4(),
            "physician",
            NOW,
            uuid4(),
            None,
        )


def test_cath_lab_review_requires_workflow_authorization_and_revocation_source() -> None:
    base = dict(
        decision_id=uuid4(),
        clinical_case_id=uuid4(),
        snapshot_id=uuid4(),
        assessment_id=uuid4(),
        decision_type=ClinicalDecisionType.REQUEST_CATH_LAB_REVIEW,
        revision_number=1,
        record_version=1,
        rationale="Physician review request.",
        uncertainty="Further specialist review required.",
        evidence_references=("ecg:1:v1",),
        actor_id=uuid4(),
        actor_role="physician",
        recorded_at=NOW,
    )
    with pytest.raises(DomainInvariantError, match="workflow authorization"):
        PhysicianDecision(status=DecisionRecordStatus.ACTIVE, **base)
    active = PhysicianDecision(
        status=DecisionRecordStatus.ACTIVE, workflow_authorization_id=uuid4(), **base
    )
    with pytest.raises(DomainInvariantError, match="source and reason"):
        PhysicianDecision(
            **{**base, "decision_id": uuid4(), "revision_number": 2},
            status=DecisionRecordStatus.REVOCATION,
        )
    assert active.status is DecisionRecordStatus.ACTIVE
