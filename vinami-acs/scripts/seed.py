"""Create deterministic synthetic R1 lifecycle data through application handlers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid5

from vinami.clinical_case.application.lifecycle import (
    OpenClinicalCase,
    OpenClinicalCaseHandler,
)
from vinami.clinical_case.application.lifecycle import (
    UnitOfWorkFactory as ClinicalCaseUnitOfWorkFactory,
)
from vinami.clinical_case.domain.model import ClinicalPriority
from vinami.identity.adapters.development import DevelopmentIdentityAdapter
from vinami.identity.domain.model import ClinicalRole, ClinicalUser
from vinami.patient.application.lifecycle import (
    RegisterPatient,
    RegisterPatientHandler,
    SafeDemographicSummary,
    StartEncounter,
    StartEncounterHandler,
)
from vinami.patient.application.lifecycle import (
    UnitOfWorkFactory as PatientUnitOfWorkFactory,
)
from vinami.shared.actor import ActorContext
from vinami.shared.config import Settings
from vinami.shared.container import AppContainer
from vinami.shared.logging import log_event
from vinami.triage.application.use_cases import (
    CorrectTriageAssessment,
    CorrectTriageAssessmentHandler,
    CorrectVitalObservationSet,
    CorrectVitalObservationSetHandler,
    RecordTriageAssessment,
    RecordTriageAssessmentHandler,
    RecordVitalObservationSet,
    RecordVitalObservationSetHandler,
    TriageContent,
    VitalContent,
)
from vinami.triage.application.use_cases import (
    UnitOfWorkFactory as DocumentationUnitOfWorkFactory,
)
from vinami.triage.domain.model import (
    DataQualityStatus,
    ObservationState,
    OnsetPrecision,
    StructuredObservation,
    VitalKind,
    VitalMeasurement,
)

SEED_NAMESPACE = UUID("62e2f5a0-98d8-4c59-bde8-35521ea06110")
ACTOR_ID = uuid5(SEED_NAMESPACE, "r1-development-actor")
BASE_TIME = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)

CASES = (
    (
        "high-priority-review",
        "45-64",
        "female",
        "Emergency Department",
        ClinicalPriority.CRITICAL,
    ),
    ("observation", "65-74", "male", "Observation Unit", ClinicalPriority.ROUTINE),
    ("repeat-assessment", "35-44", None, "Emergency Department", ClinicalPriority.URGENT),
)


def main() -> None:
    """Seed three lifecycle-only cases idempotently and project their audit/timeline."""
    container = AppContainer.create(Settings())
    try:
        container.database.probe_readiness()
        DevelopmentIdentityAdapter(container.database.session_factory).ensure_actor(
            ClinicalUser(
                id=ACTOR_ID,
                display_name="R1 Development Seed Actor",
                role=ClinicalRole.COORDINATOR,
            )
        )
        patient_factory = cast(PatientUnitOfWorkFactory, container.unit_of_work)
        case_factory = cast(ClinicalCaseUnitOfWorkFactory, container.unit_of_work)
        patient_handler = RegisterPatientHandler(patient_factory)
        encounter_handler = StartEncounterHandler(patient_factory)
        case_handler = OpenClinicalCaseHandler(case_factory)
        documentation_factory = cast(DocumentationUnitOfWorkFactory, container.unit_of_work)
        triage_handler = RecordTriageAssessmentHandler(documentation_factory)
        correct_triage_handler = CorrectTriageAssessmentHandler(documentation_factory)
        vital_handler = RecordVitalObservationSetHandler(documentation_factory)
        correct_vital_handler = CorrectVitalObservationSetHandler(documentation_factory)
        case_ids: list[str] = []
        for index, (name, age_band, sex, location, priority) in enumerate(CASES):
            occurred_at = BASE_TIME + timedelta(minutes=index * 10)
            actor = ActorContext(
                actor_id=ACTOR_ID,
                actor_role=ClinicalRole.COORDINATOR.value,
                correlation_id=uuid5(SEED_NAMESPACE, f"correlation:{name}"),
                request_source="deterministic-r1-seed",
            )
            patient = patient_handler.execute(
                RegisterPatient(
                    command_id=uuid5(SEED_NAMESPACE, f"command:patient:{name}"),
                    actor=actor,
                    idempotency_key=f"r1-seed-patient-{name}",
                    patient_reference=f"R1-SYN-{index + 1:03d}",
                    safe_demographic_summary=SafeDemographicSummary(age_band, sex),
                    requested_at=occurred_at,
                    patient_id=uuid5(SEED_NAMESPACE, f"patient:{name}"),
                )
            )
            encounter = encounter_handler.execute(
                StartEncounter(
                    command_id=uuid5(SEED_NAMESPACE, f"command:encounter:{name}"),
                    actor=actor,
                    idempotency_key=f"r1-seed-encounter-{name}",
                    patient_id=patient.patient_id,
                    location=location,
                    arrival_at=occurred_at + timedelta(minutes=1),
                    external_reference=f"R1-ENC-{index + 1:03d}",
                    encounter_id=uuid5(SEED_NAMESPACE, f"encounter:{name}"),
                )
            )
            clinical_case = case_handler.execute(
                OpenClinicalCase(
                    command_id=uuid5(SEED_NAMESPACE, f"command:case:{name}"),
                    actor=actor,
                    idempotency_key=f"r1-seed-case-{name}",
                    encounter_id=encounter.encounter_id,
                    opening_reason=f"R1 synthetic {name} lifecycle demonstration",
                    priority=priority,
                    requested_at=occurred_at + timedelta(minutes=2),
                    case_id=uuid5(SEED_NAMESPACE, f"case:{name}"),
                )
            )
            _seed_r2_documentation(
                index=index,
                name=name,
                actor=actor,
                case_id=clinical_case.case_id,
                case_version=clinical_case.aggregate_version,
                triage_handler=triage_handler,
                correct_triage_handler=correct_triage_handler,
                vital_handler=vital_handler,
                correct_vital_handler=correct_vital_handler,
                occurred_at=occurred_at + timedelta(minutes=3),
            )
            case_ids.append(str(clinical_case.case_id))
        dispatch = container.event_dispatcher().dispatch_pending(limit=100)
        log_event(
            container.logger,
            "r1_seed_completed",
            clinical_cases=case_ids,
            events_published=dispatch.published,
            dead_lettered=dispatch.dead_lettered,
        )
        if dispatch.dead_lettered:
            raise RuntimeError("R1 seed produced a dead-letter event")
    finally:
        container.database.dispose()


def _seed_r2_documentation(
    *,
    index: int,
    name: str,
    actor: ActorContext,
    case_id: UUID,
    case_version: int,
    triage_handler: RecordTriageAssessmentHandler,
    correct_triage_handler: CorrectTriageAssessmentHandler,
    vital_handler: RecordVitalObservationSetHandler,
    correct_vital_handler: CorrectVitalObservationSetHandler,
    occurred_at: datetime,
) -> None:
    """Seed complete, incomplete, and corrected synthetic documentation scenarios."""
    triage_contents = (
        TriageContent(
            chief_complaint="Synthetic chest discomfort documentation",
            symptom_onset_state=ObservationState.PRESENT,
            symptom_onset_at=occurred_at - timedelta(minutes=40),
            symptom_onset_precision=OnsetPrecision.APPROXIMATE,
            symptom_description="Synthetic patient-reported pressure sensation",
            associated_symptoms=(
                StructuredObservation("dyspnoea", ObservationState.ABSENT),
                StructuredObservation("nausea", ObservationState.UNKNOWN),
            ),
        ),
        TriageContent(
            symptom_onset_state=ObservationState.NOT_ASSESSED,
            associated_symptoms=(StructuredObservation("dyspnoea", ObservationState.UNKNOWN),),
            clinical_note="Synthetic incomplete documentation example",
        ),
        TriageContent(
            chief_complaint="Synthetic initial symptom wording",
            symptom_onset_state=ObservationState.UNKNOWN,
            cardiovascular_risk_factors=(
                StructuredObservation("smoking history", ObservationState.NOT_ASSESSED),
            ),
        ),
    )
    triage = triage_handler.execute(
        RecordTriageAssessment(
            command_id=uuid5(SEED_NAMESPACE, f"r2-command:triage:{name}"),
            actor=actor,
            idempotency_key=f"r2-seed-triage-{name}",
            clinical_case_id=case_id,
            expected_case_version=case_version,
            occurred_at=occurred_at,
            source="deterministic-r2-seed",
            content=triage_contents[index],
            assessment_id=uuid5(SEED_NAMESPACE, f"r2-triage:{name}"),
        )
    )
    if index == 2:
        correct_triage_handler.execute(
            CorrectTriageAssessment(
                command_id=uuid5(SEED_NAMESPACE, f"r2-command:triage-correction:{name}"),
                actor=actor,
                idempotency_key=f"r2-seed-triage-correction-{name}",
                clinical_case_id=case_id,
                assessment_id=triage.assessment.id,
                expected_record_version=triage.assessment.record_version,
                occurred_at=occurred_at + timedelta(minutes=2),
                source="deterministic-r2-seed-correction",
                correction_reason="Synthetic clarification entered for correction demo",
                content=TriageContent(
                    chief_complaint="Synthetic clarified symptom wording",
                    symptom_onset_state=ObservationState.ABSENT,
                    cardiovascular_risk_factors=(
                        StructuredObservation("smoking history", ObservationState.UNKNOWN),
                    ),
                ),
                correction_id=uuid5(SEED_NAMESPACE, f"r2-triage-correction:{name}"),
            )
        )

    vital_handler.execute(
        RecordVitalObservationSet(
            command_id=uuid5(SEED_NAMESPACE, f"r2-command:vitals-1:{name}"),
            actor=actor,
            idempotency_key=f"r2-seed-vitals-1-{name}",
            clinical_case_id=case_id,
            expected_case_version=case_version,
            observed_at=occurred_at + timedelta(minutes=1),
            source="deterministic-r2-seed",
            content=_vital_content(index, occurred_at + timedelta(minutes=1)),
            vital_set_id=uuid5(SEED_NAMESPACE, f"r2-vitals-1:{name}"),
        )
    )
    if index == 0:
        return

    repeated = vital_handler.execute(
        RecordVitalObservationSet(
            command_id=uuid5(SEED_NAMESPACE, f"r2-command:vitals-2:{name}"),
            actor=actor,
            idempotency_key=f"r2-seed-vitals-2-{name}",
            clinical_case_id=case_id,
            expected_case_version=case_version,
            observed_at=occurred_at + timedelta(minutes=16),
            source="deterministic-r2-seed",
            content=_vital_content(index + 1, occurred_at + timedelta(minutes=16)),
            vital_set_id=uuid5(SEED_NAMESPACE, f"r2-vitals-2:{name}"),
        )
    )
    if index == 2:
        correct_vital_handler.execute(
            CorrectVitalObservationSet(
                command_id=uuid5(SEED_NAMESPACE, f"r2-command:vitals-correction:{name}"),
                actor=actor,
                idempotency_key=f"r2-seed-vitals-correction-{name}",
                clinical_case_id=case_id,
                vital_set_id=repeated.vital_set.id,
                expected_record_version=repeated.vital_set.record_version,
                observed_at=occurred_at + timedelta(minutes=16),
                source="deterministic-r2-seed-correction",
                correction_reason="Synthetic source row corrected for demonstration",
                content=_vital_content(index + 2, occurred_at + timedelta(minutes=16)),
                correction_id=uuid5(SEED_NAMESPACE, f"r2-vitals-correction:{name}"),
            )
        )


def _vital_content(index: int, observed_at: datetime) -> VitalContent:
    return VitalContent(
        measurements=(
            VitalMeasurement(
                kind=VitalKind.HEART_RATE,
                value=float(70 + index),
                unit="beats/min",
                source="synthetic-manual-entry",
                observed_at=observed_at,
                quality_status=DataQualityStatus.ACCEPTED,
            ),
            VitalMeasurement(
                kind=VitalKind.SYSTOLIC_BLOOD_PRESSURE,
                value=float(118 + index),
                unit="mmHg",
                source="synthetic-manual-entry",
                observed_at=observed_at,
                quality_status=DataQualityStatus.ACCEPTED,
            ),
            VitalMeasurement(
                kind=VitalKind.DIASTOLIC_BLOOD_PRESSURE,
                value=float(76 + index),
                unit="mmHg",
                source="synthetic-manual-entry",
                observed_at=observed_at,
                quality_status=DataQualityStatus.ACCEPTED,
            ),
        ),
        device_reference="synthetic-device",
        supplemental_oxygen_state=ObservationState.NOT_ASSESSED,
    )


if __name__ == "__main__":
    main()
