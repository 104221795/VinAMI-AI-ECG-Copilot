"""Domain tests for non-diagnostic R2 clinical documentation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from vinami.shared.domain import DomainInvariantError
from vinami.shared.events.contracts import EventContext
from vinami.triage.domain.model import (
    DataQualityStatus,
    ObservationState,
    OnsetPrecision,
    StructuredObservation,
    TriageAssessment,
    VitalKind,
    VitalMeasurement,
    VitalObservationSet,
)

NOW = datetime(2026, 7, 14, 8, 0, tzinfo=UTC)


def _context() -> EventContext:
    return EventContext(correlation_id=uuid4(), actor_id=uuid4())


def _measurement(kind: VitalKind = VitalKind.HEART_RATE) -> VitalMeasurement:
    units = {
        VitalKind.HEART_RATE: "beats/min",
        VitalKind.SYSTOLIC_BLOOD_PRESSURE: "mmHg",
    }
    return VitalMeasurement(
        kind=kind,
        value=72.0,
        unit=units[kind],
        source="manual-entry",
        observed_at=NOW,
        quality_status=DataQualityStatus.ACCEPTED,
    )


def test_triage_preserves_explicit_absent_unknown_and_not_assessed_states() -> None:
    assessment = TriageAssessment.record(
        assessment_id=uuid4(),
        clinical_case_id=uuid4(),
        source="triage-form",
        actor_id=uuid4(),
        actor_role="nurse",
        occurred_at=NOW,
        recorded_at=NOW,
        context=_context(),
        symptom_onset_state=ObservationState.UNKNOWN,
        associated_symptoms=(
            StructuredObservation("dyspnoea", ObservationState.ABSENT),
            StructuredObservation("nausea", ObservationState.NOT_ASSESSED),
        ),
    )

    assert assessment.symptom_onset_state is ObservationState.UNKNOWN
    assert [item.state for item in assessment.associated_symptoms] == [
        ObservationState.ABSENT,
        ObservationState.NOT_ASSESSED,
    ]
    assert assessment.pull_events()[0].event_type == "TriageAssessmentRecorded.v1"


def test_present_onset_requires_utc_timestamp_and_precision() -> None:
    with pytest.raises(DomainInvariantError, match="present symptom onset"):
        TriageAssessment.record(
            assessment_id=uuid4(),
            clinical_case_id=uuid4(),
            source="triage-form",
            actor_id=uuid4(),
            actor_role="nurse",
            occurred_at=NOW,
            recorded_at=NOW,
            context=_context(),
            symptom_onset_state=ObservationState.PRESENT,
        )


def test_triage_correction_is_a_new_revision_with_provenance() -> None:
    original = TriageAssessment.record(
        assessment_id=uuid4(),
        clinical_case_id=uuid4(),
        source="triage-form",
        actor_id=uuid4(),
        actor_role="nurse",
        occurred_at=NOW,
        recorded_at=NOW,
        context=_context(),
        symptom_onset_state=ObservationState.PRESENT,
        symptom_onset_at=NOW,
        symptom_onset_precision=OnsetPrecision.APPROXIMATE,
    )
    correction = original.corrected(
        assessment_id=uuid4(),
        source="triage-correction",
        actor_id=uuid4(),
        actor_role="physician",
        occurred_at=NOW,
        recorded_at=NOW,
        reason="Patient clarified onset time",
        context=_context(),
        symptom_onset_state=ObservationState.UNKNOWN,
    )

    assert correction.id != original.id
    assert correction.corrects_assessment_id == original.id
    assert correction.revision_number == original.revision_number + 1
    assert correction.record_version == original.record_version + 1
    assert correction.pull_events()[0].event_type == "TriageAssessmentCorrected.v1"


def test_vital_measurement_rejects_unsupported_unit_and_naive_time() -> None:
    with pytest.raises(DomainInvariantError, match="unsupported unit"):
        VitalMeasurement(
            kind=VitalKind.HEART_RATE,
            value=72,
            unit="bpm",
            source="manual-entry",
            observed_at=NOW,
        )
    with pytest.raises(DomainInvariantError, match="timezone-aware"):
        VitalMeasurement(
            kind=VitalKind.HEART_RATE,
            value=72,
            unit="beats/min",
            source="manual-entry",
            observed_at=datetime(2026, 7, 14, 8, 0),
        )


def test_vital_set_rejects_duplicate_kind() -> None:
    duplicate = _measurement()
    with pytest.raises(DomainInvariantError, match="repeat a measurement kind"):
        VitalObservationSet.record(
            vital_set_id=uuid4(),
            clinical_case_id=uuid4(),
            encounter_id=uuid4(),
            sequence_number=1,
            source="bedside-monitor",
            actor_id=uuid4(),
            actor_role="nurse",
            observed_at=NOW,
            recorded_at=NOW,
            measurements=(duplicate, duplicate),
            context=_context(),
        )


def test_vital_correction_is_append_only() -> None:
    original = VitalObservationSet.record(
        vital_set_id=uuid4(),
        clinical_case_id=uuid4(),
        encounter_id=uuid4(),
        sequence_number=2,
        source="bedside-monitor",
        actor_id=uuid4(),
        actor_role="nurse",
        observed_at=NOW,
        recorded_at=NOW,
        measurements=(_measurement(),),
        context=_context(),
    )
    correction = original.corrected(
        vital_set_id=uuid4(),
        source="manual-correction",
        actor_id=uuid4(),
        actor_role="nurse",
        observed_at=NOW,
        recorded_at=NOW,
        measurements=(_measurement(VitalKind.SYSTOLIC_BLOOD_PRESSURE),),
        reason="Wrong monitor row selected",
        context=_context(),
    )

    assert correction.id != original.id
    assert correction.corrects_vital_set_id == original.id
    assert correction.sequence_number == original.sequence_number
    assert correction.revision_number == 2
    assert original.measurements[0].kind is VitalKind.HEART_RATE
    assert correction.pull_events()[0].event_type == "VitalObservationSetCorrected.v1"
