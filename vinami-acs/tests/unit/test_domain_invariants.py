"""Fast, framework-free invariant tests for the Sprint 3 aggregates."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from vinami.clinical_case.domain.model import (
    CaseClosureAuthorization,
    ClinicalCase,
    ClinicalPriority,
)
from vinami.ecg.domain.model import ECGAcquisitionMetadata, ECGAIResult, ECGFinding, ECGStudy
from vinami.patient.domain.model import (
    Demographics,
    Encounter,
    Patient,
    PatientIdentifier,
    PersonName,
)
from vinami.shared.domain import DomainInvariantError, OptimisticConcurrencyError
from vinami.troponin.domain.model import TroponinAssay, TroponinMeasurement, TroponinTimeline

NOW = datetime(2026, 7, 13, 0, 0, tzinfo=UTC)


def test_case_requires_review_and_current_version_before_closure() -> None:
    """A case cannot be closed from open state or through a stale command."""
    case = ClinicalCase.open(uuid4(), "reported chest discomfort", ClinicalPriority.URGENT, NOW)
    actor_id = uuid4()

    def authorization(expected_version: int) -> CaseClosureAuthorization:
        return CaseClosureAuthorization(
            command_id=uuid4(),
            expected_version=expected_version,
            actor_id=actor_id,
            actor_role="physician",
            reason="review completed",
            workflow_state="DISCHARGE_REVIEW",
            physician_decision_id=uuid4(),
            disposition_outcome_id=uuid4(),
            unresolved_critical_alerts=0,
            unresolved_consequential_tasks=0,
            correlation_id=uuid4(),
            causation_id=None,
            occurred_at=NOW,
        )

    with pytest.raises(DomainInvariantError, match="reviewed"):
        case.close(authorization(1))

    case.begin_review(expected_version=1)
    with pytest.raises(OptimisticConcurrencyError):
        case.close(authorization(1))

    case.close(authorization(2))
    assert case.version == 3
    assert case.pull_events()[-1].event_type == "CaseClosed.v1"


def test_ecg_result_requires_matching_immutable_input_reference() -> None:
    """An AI result cannot be attached to another ECG study's evidence reference."""
    study = ECGStudy.upload(
        case_id=uuid4(),
        input_reference="evidence://ecg/one",
        media_type="application/wfdb",
        metadata=ECGAcquisitionMetadata("demo", 500, 12, NOW),
        uploaded_at=NOW,
    )
    result = ECGAIResult(
        model_name="prototype",
        model_version="1.0",
        input_reference="evidence://ecg/two",
        analyzed_at=NOW,
        findings=(ECGFinding("NORM", 0.7),),
        limitations="Research evidence only.",
    )

    with pytest.raises(DomainInvariantError, match="does not match"):
        study.record_ai_result(result)


def test_troponin_result_requires_order_and_collection() -> None:
    """Timeline order and collection provenance are mandatory before a result."""
    timeline = TroponinTimeline.create(uuid4())
    measurement = TroponinMeasurement(
        uuid4(), 10.0, TroponinAssay("hs-cTn", "ng/L"), NOW, NOW, "lab-1"
    )

    with pytest.raises(DomainInvariantError, match="collected"):
        timeline.record_result(measurement)

    timeline.order("lab-1")
    timeline.collect("lab-1", NOW)
    timeline.record_result(measurement)
    assert timeline.measurements == [measurement]


def test_case_closure_rejects_unresolved_safety_evidence() -> None:
    """Critical alerts and consequential tasks independently block domain closure."""
    case = ClinicalCase.open(uuid4(), "reported chest discomfort", ClinicalPriority.URGENT, NOW)
    case.begin_review(1)
    base = {
        "command_id": uuid4(),
        "expected_version": 2,
        "actor_id": uuid4(),
        "actor_role": "physician",
        "reason": "review completed",
        "workflow_state": "DISCHARGE_REVIEW",
        "physician_decision_id": uuid4(),
        "disposition_outcome_id": uuid4(),
        "correlation_id": uuid4(),
        "causation_id": None,
        "occurred_at": NOW,
    }
    with pytest.raises(DomainInvariantError, match="critical alerts"):
        case.close(
            CaseClosureAuthorization(
                **base,
                unresolved_critical_alerts=1,
                unresolved_consequential_tasks=0,
            )
        )
    with pytest.raises(DomainInvariantError, match="consequential tasks"):
        case.close(
            CaseClosureAuthorization(
                **base,
                unresolved_critical_alerts=0,
                unresolved_consequential_tasks=1,
            )
        )


def test_patient_and_encounter_events_use_utc_domain_provenance() -> None:
    """Patient/encounter lifecycle events retain UUID and UTC facts."""
    patient = Patient.register(
        PatientIdentifier("vinami-demo", "P-001"),
        PersonName("An", "Nguyen"),
        Demographics(None, None),
        NOW,
    )
    encounter = Encounter.start(patient.id, "Emergency", NOW)

    assert patient.pull_events()[0].occurred_at.tzinfo is UTC
    assert encounter.pull_events()[0].payload["patient_id"] == str(patient.id)
