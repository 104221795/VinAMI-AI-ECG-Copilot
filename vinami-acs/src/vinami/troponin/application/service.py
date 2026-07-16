"""R4 application services for troponin evidence; no diagnostic reasoning is performed."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from vinami.clinical_case.domain.model import CaseStatus
from vinami.shared.actor import ActorContext
from vinami.shared.application_errors import ResourceConflictError, ResourceNotFoundError
from vinami.shared.domain import DomainInvariantError, require_text, require_utc, utc_now
from vinami.shared.events.contracts import EventContext, EventEnvelope
from vinami.shared.idempotency import IdempotencyResult, command_fingerprint
from vinami.troponin.adapters.r4_persistence import (
    ClinicianTroponinReviewRecord,
    LaboratoryImportJobRecord,
    RepeatTroponinRequestRecord,
    TroponinAssayRecord,
    TroponinEvidenceRecord,
)
from vinami.troponin.domain.evidence import ResultStatus, UnitConversionPolicy, calculate_delta
from vinami.troponin.ports.laboratory import LaboratoryConnectorError, LaboratoryResultConnector


class UnitOfWork(Protocol):
    cases: Any
    actors: Any
    idempotency: Any
    troponin_evidence: Any

    def __enter__(self) -> UnitOfWork: ...
    def __exit__(self, *args: object) -> None: ...
    def stage_event(self, event: EventEnvelope) -> None: ...
    def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class RecordTroponinResult:
    case_id: UUID
    assay_code: str
    analyte: str
    value: str
    unit: str
    specimen_type: str
    specimen_collected_at: datetime
    resulted_at: datetime
    result_status: str
    reference_limit_value: str | None
    reference_limit_unit: str | None
    reference_limit_source: str | None
    quality_flags: tuple[str, ...]
    source_system: str
    source_result_id: str
    accession_number: str | None
    note: str | None
    expected_case_version: int
    actor: ActorContext
    idempotency_key: str


class TroponinApplicationService:
    def __init__(
        self,
        uow_factory: Any,
        connectors: Mapping[str, LaboratoryResultConnector],
    ) -> None:
        self._uow_factory = uow_factory
        self._connectors = dict(connectors)

    def record_result(self, command: RecordTroponinResult) -> dict[str, object]:
        payload = {
            key: value
            for key, value in asdict(command).items()
            if key not in {"actor", "idempotency_key"}
        }
        return self._record(command, "RecordTroponinResult", command_fingerprint(payload))

    def amend_result(
        self,
        result_id: UUID,
        *,
        value: str,
        unit: str,
        status: str,
        reason: str,
        resulted_at: datetime,
        expected_version: int,
        actor: ActorContext,
        idempotency_key: str,
    ) -> dict[str, object]:
        fingerprint = command_fingerprint(
            {
                "result_id": result_id,
                "value": value,
                "unit": unit,
                "status": status,
                "reason": reason,
                "resulted_at": resulted_at,
                "expected_version": expected_version,
            }
        )
        with self._uow_factory() as uow:
            existing = self._idempotent(
                uow, actor, "AmendTroponinResult", idempotency_key, fingerprint
            )
            if existing:
                return dict(existing.response_payload)
            original = uow.troponin_evidence.session.get(TroponinEvidenceRecord, result_id)
            if original is None:
                raise ResourceNotFoundError("troponin result was not found")
            if original.record_version != expected_version:
                raise ResourceConflictError("stale troponin result version")
            assay = uow.troponin_evidence.session.get(TroponinAssayRecord, original.assay_id)
            normalized = UnitConversionPolicy.normalize(
                UnitConversionPolicy.decimal(value), unit, assay.canonical_unit
            )
            now = utc_now()
            amended = TroponinEvidenceRecord(
                result_id=uuid4(),
                clinical_case_id=original.clinical_case_id,
                assay_id=original.assay_id,
                analyte=original.analyte,
                original_value=normalized.original_value,
                original_unit=normalized.original_unit,
                normalized_value=normalized.normalized_value,
                normalized_unit=normalized.normalized_unit,
                conversion_status=normalized.conversion_status,
                conversion_version=normalized.conversion_version,
                specimen_type=original.specimen_type,
                specimen_collected_at=original.specimen_collected_at,
                resulted_at=require_utc(resulted_at, "resulted_at"),
                result_status=ResultStatus(status).value,
                reference_limit_value=original.reference_limit_value,
                reference_limit_unit=original.reference_limit_unit,
                reference_limit_source=original.reference_limit_source,
                quality_flags=list(original.quality_flags),
                source_system=original.source_system,
                source_type=original.source_type,
                source_result_id=f"{original.source_result_id}:amendment:{uuid4()}",
                source_identity=f"manual-amendment:{uuid4()}",
                source_revision=1,
                accession_number=original.accession_number,
                note=original.note,
                supersedes_result_id=original.result_id,
                amendment_reason=require_text(reason, "amendment_reason"),
                recorded_by_actor_id=actor.actor_id,
                recorded_by_role=actor.actor_role,
                recorded_at=now,
                correlation_id=actor.correlation_id,
                record_version=1,
            )
            uow.troponin_evidence.session.add(amended)
            response = self._result_dict(amended, assay)
            self._stage(
                uow,
                "TroponinResultAmended.v1",
                amended.result_id,
                1,
                amended.clinical_case_id,
                actor,
                {
                    "result_id": str(amended.result_id),
                    "supersedes_result_id": str(result_id),
                    "amendment_reason": amended.amendment_reason,
                },
            )
            self._store(
                uow,
                actor,
                "AmendTroponinResult",
                idempotency_key,
                fingerprint,
                amended.result_id,
                response,
                now,
            )
            uow.commit()
            return response

    def import_result(
        self,
        case_id: UUID,
        connector_id: str,
        external_reference: str,
        expected_case_version: int,
        actor: ActorContext,
        idempotency_key: str,
    ) -> dict[str, object]:
        connector = self._connectors.get(connector_id)
        if connector is None:
            raise ResourceNotFoundError("laboratory connector was not found")
        fingerprint = command_fingerprint(
            {
                "case_id": case_id,
                "connector_id": connector_id,
                "external_reference": external_reference,
                "expected_case_version": expected_case_version,
            }
        )
        now = utc_now()
        with self._uow_factory() as uow:
            prior = self._idempotent(
                uow, actor, "ImportTroponinResult", idempotency_key, fingerprint
            )
            if prior:
                return dict(prior.response_payload)
            self._case(uow, case_id, expected_case_version)
            job = LaboratoryImportJobRecord(
                import_job_id=uuid4(),
                clinical_case_id=case_id,
                connector_id=connector_id,
                external_reference=require_text(external_reference, "external_reference"),
                status="receiving",
                requested_by_actor_id=actor.actor_id,
                requested_by_actor_role=actor.actor_role,
                requested_at=now,
                started_at=now,
                completed_at=None,
                source_message_reference=None,
                resulting_result_ids=[],
                parser_name="VinAMILocalLaboratoryProfileParser",
                parser_version="1",
                warnings=[],
                failure_category=None,
                failure_detail_safe=None,
                retry_count=0,
                idempotency_key=idempotency_key,
                correlation_id=actor.correlation_id,
                record_version=1,
            )
            uow.troponin_evidence.session.add(job)
            try:
                parsed = connector.parse_result(connector.fetch_result(external_reference))
                assay = uow.troponin_evidence.assay_by_code(str(parsed["assay_code"]))
                if assay is None:
                    raise DomainInvariantError("unsupported assay definition")
                source_identity, source_revision = self._source_delivery_identity(parsed)
                duplicate = uow.troponin_evidence.source_revision(
                    connector_id, source_identity, source_revision
                )
                if duplicate is None:
                    supersedes_result_id = self._source_predecessor(
                        uow, connector_id, source_identity, source_revision, parsed
                    )
                    recorded = self._make_record(
                        case_id,
                        assay,
                        parsed,
                        actor,
                        now,
                        connector_id,
                        "laboratory",
                        source_identity=source_identity,
                        source_revision=source_revision,
                        supersedes_result_id=supersedes_result_id,
                    )
                    uow.troponin_evidence.session.add(recorded)
                    job.resulting_result_ids = [str(recorded.result_id)]
                    self._stage(
                        uow,
                        self._source_delivery_event(recorded.result_status),
                        recorded.result_id,
                        1,
                        case_id,
                        actor,
                        {
                            "case_id": str(case_id),
                            "result_id": str(recorded.result_id),
                            "import_job_id": str(job.import_job_id),
                            "source_identity": source_identity,
                            "source_revision": source_revision,
                        },
                    )
                else:
                    job.resulting_result_ids = [str(duplicate.result_id)]
                    job.warnings = ["Duplicate source delivery reused the existing result."]
                job.status = "completed_with_warning" if job.warnings else "completed"
                job.completed_at = utc_now()
                self._stage(
                    uow,
                    "LaboratoryImportCompleted.v1",
                    job.import_job_id,
                    1,
                    case_id,
                    actor,
                    {
                        "case_id": str(case_id),
                        "import_job_id": str(job.import_job_id),
                        "result_ids": job.resulting_result_ids,
                    },
                )
            except LaboratoryConnectorError as error:
                job.status = "failed"
                job.completed_at = utc_now()
                job.failure_category = error.category
                job.failure_detail_safe = str(error)[:500]
                self._stage(
                    uow,
                    "LaboratoryImportFailed.v1",
                    job.import_job_id,
                    1,
                    case_id,
                    actor,
                    {
                        "case_id": str(case_id),
                        "import_job_id": str(job.import_job_id),
                        "failure_category": error.category,
                    },
                )
            except DomainInvariantError as error:
                job.status = "rejected"
                job.completed_at = utc_now()
                job.failure_category = "validation"
                job.failure_detail_safe = str(error)[:500]
                self._stage(
                    uow,
                    "LaboratoryImportFailed.v1",
                    job.import_job_id,
                    1,
                    case_id,
                    actor,
                    {
                        "case_id": str(case_id),
                        "import_job_id": str(job.import_job_id),
                        "failure_category": "validation",
                    },
                )
            response = self._job_dict(job)
            self._store(
                uow,
                actor,
                "ImportTroponinResult",
                idempotency_key,
                fingerprint,
                job.import_job_id,
                response,
                now,
            )
            uow.commit()
            return response

    def record_review(
        self,
        case_id: UUID,
        result_ids: list[UUID],
        review_status: str,
        incompatibility_acknowledged: bool,
        quality_limitation_acknowledged: bool,
        repeat_requested: bool,
        repeat_reason: str | None,
        note: str | None,
        occurred_at: datetime,
        expected_case_version: int,
        actor: ActorContext,
        idempotency_key: str,
    ) -> dict[str, object]:
        fingerprint = command_fingerprint(locals())
        with self._uow_factory() as uow:
            prior = self._idempotent(
                uow, actor, "RecordClinicianTroponinReview", idempotency_key, fingerprint
            )
            if prior:
                return dict(prior.response_payload)
            self._case(uow, case_id, expected_case_version)
            if not result_ids:
                raise DomainInvariantError("clinician review requires at least one result")
            records = [
                uow.troponin_evidence.session.get(TroponinEvidenceRecord, item)
                for item in result_ids
            ]
            if any(item is None or item.clinical_case_id != case_id for item in records):
                raise ResourceNotFoundError(
                    "one or more troponin results were not found for this case"
                )
            if repeat_requested and not repeat_reason:
                raise DomainInvariantError("repeat measurement reason is required")
            now = utc_now()
            review = ClinicianTroponinReviewRecord(
                review_id=uuid4(),
                clinical_case_id=case_id,
                referenced_result_ids=[str(item) for item in result_ids],
                actor_id=actor.actor_id,
                actor_role=actor.actor_role,
                review_status=require_text(review_status, "review_status"),
                incompatibility_acknowledged=incompatibility_acknowledged,
                quality_limitation_acknowledged=quality_limitation_acknowledged,
                repeat_measurement_requested=repeat_requested,
                repeat_measurement_reason=repeat_reason,
                note=note,
                occurred_at=require_utc(occurred_at, "occurred_at"),
                recorded_at=now,
                correlation_id=actor.correlation_id,
                supersedes_review_id=None,
                record_version=1,
            )
            uow.troponin_evidence.session.add(review)
            request = None
            if repeat_requested:
                request = RepeatTroponinRequestRecord(
                    request_id=uuid4(),
                    clinical_case_id=case_id,
                    source_result_id=result_ids[-1],
                    requested_by_actor_id=actor.actor_id,
                    reason=require_text(repeat_reason or "", "repeat_reason"),
                    requested_at=now,
                    status="requested",
                    acknowledged_by_actor_id=None,
                    acknowledged_at=None,
                    completed_result_id=None,
                    completed_at=None,
                    cancellation_reason=None,
                    correlation_id=actor.correlation_id,
                    record_version=1,
                )
                uow.troponin_evidence.session.add(request)
                self._stage(
                    uow,
                    "RepeatTroponinMeasurementRequested.v1",
                    request.request_id,
                    1,
                    case_id,
                    actor,
                    {
                        "case_id": str(case_id),
                        "request_id": str(request.request_id),
                        "source_result_id": str(request.source_result_id),
                    },
                )
            response = self._review_dict(review, request)
            self._stage(
                uow,
                "ClinicianTroponinReviewRecorded.v1",
                review.review_id,
                1,
                case_id,
                actor,
                {
                    "case_id": str(case_id),
                    "review_id": str(review.review_id),
                    "repeat_measurement_requested": repeat_requested,
                },
            )
            self._store(
                uow,
                actor,
                "RecordClinicianTroponinReview",
                idempotency_key,
                fingerprint,
                review.review_id,
                response,
                now,
            )
            uow.commit()
            return response

    def correct_review(
        self,
        case_id: UUID,
        review_id: UUID,
        result_ids: list[UUID],
        review_status: str,
        incompatibility_acknowledged: bool,
        quality_limitation_acknowledged: bool,
        repeat_requested: bool,
        repeat_reason: str | None,
        correction_reason: str,
        note: str | None,
        occurred_at: datetime,
        expected_case_version: int,
        expected_review_version: int,
        actor: ActorContext,
        idempotency_key: str,
    ) -> dict[str, object]:
        fingerprint = command_fingerprint(
            {
                "case_id": case_id,
                "review_id": review_id,
                "result_ids": result_ids,
                "review_status": review_status,
                "incompatibility_acknowledged": incompatibility_acknowledged,
                "quality_limitation_acknowledged": quality_limitation_acknowledged,
                "repeat_requested": repeat_requested,
                "repeat_reason": repeat_reason,
                "correction_reason": correction_reason,
                "note": note,
                "occurred_at": occurred_at,
                "expected_case_version": expected_case_version,
                "expected_review_version": expected_review_version,
            }
        )
        with self._uow_factory() as uow:
            prior = self._idempotent(
                uow, actor, "CorrectClinicianTroponinReview", idempotency_key, fingerprint
            )
            if prior:
                return dict(prior.response_payload)
            self._case(uow, case_id, expected_case_version)
            original = uow.troponin_evidence.session.get(ClinicianTroponinReviewRecord, review_id)
            if original is None or original.clinical_case_id != case_id:
                raise ResourceNotFoundError("clinician troponin review was not found for this case")
            if original.record_version != expected_review_version:
                raise ResourceConflictError("stale clinician troponin review version")
            if not result_ids:
                raise DomainInvariantError("clinician review requires at least one result")
            records = [
                uow.troponin_evidence.session.get(TroponinEvidenceRecord, item)
                for item in result_ids
            ]
            if any(item is None or item.clinical_case_id != case_id for item in records):
                raise ResourceNotFoundError(
                    "one or more troponin results were not found for this case"
                )
            if repeat_requested and not repeat_reason:
                raise DomainInvariantError("repeat measurement reason is required")
            validated_correction_reason = require_text(correction_reason, "correction_reason")
            now = utc_now()
            corrected = ClinicianTroponinReviewRecord(
                review_id=uuid4(),
                clinical_case_id=case_id,
                referenced_result_ids=[str(item) for item in result_ids],
                actor_id=actor.actor_id,
                actor_role=actor.actor_role,
                review_status=require_text(review_status, "review_status"),
                incompatibility_acknowledged=incompatibility_acknowledged,
                quality_limitation_acknowledged=quality_limitation_acknowledged,
                repeat_measurement_requested=repeat_requested,
                repeat_measurement_reason=repeat_reason,
                note=note,
                occurred_at=require_utc(occurred_at, "occurred_at"),
                recorded_at=now,
                correlation_id=actor.correlation_id,
                supersedes_review_id=original.review_id,
                correction_reason=validated_correction_reason,
                record_version=1,
            )
            uow.troponin_evidence.session.add(corrected)
            response = self._review_dict(corrected)
            self._stage(
                uow,
                "ClinicianTroponinReviewCorrected.v1",
                corrected.review_id,
                corrected.record_version,
                case_id,
                actor,
                {
                    "case_id": str(case_id),
                    "review_id": str(corrected.review_id),
                    "supersedes_review_id": str(original.review_id),
                    "correction_reason": validated_correction_reason,
                },
            )
            self._store(
                uow,
                actor,
                "CorrectClinicianTroponinReview",
                idempotency_key,
                fingerprint,
                corrected.review_id,
                response,
                now,
            )
            uow.commit()
            return response

    def retry_import(
        self, job_id: UUID, actor: ActorContext, idempotency_key: str, expected_version: int
    ) -> dict[str, object]:
        fingerprint = command_fingerprint({"job_id": job_id, "expected_version": expected_version})
        now = utc_now()
        with self._uow_factory() as uow:
            prior = self._idempotent(
                uow, actor, "RetryLaboratoryImport", idempotency_key, fingerprint
            )
            if prior:
                return dict(prior.response_payload)
            job = uow.troponin_evidence.session.get(LaboratoryImportJobRecord, job_id)
            if job is None:
                raise ResourceNotFoundError("laboratory import job was not found")
            if job.record_version != expected_version:
                raise ResourceConflictError("stale laboratory import version")
            if job.status not in {"failed", "rejected"}:
                raise ResourceConflictError("only failed or rejected imports can be retried")
            connector = self._connectors.get(job.connector_id)
            if connector is None:
                raise ResourceNotFoundError("laboratory connector was not found")
            job.status = "receiving"
            job.started_at = now
            job.completed_at = None
            job.retry_count += 1
            job.record_version += 1
            reference = (
                "success" if job.external_reference == "retry-success" else job.external_reference
            )
            try:
                parsed = connector.parse_result(connector.fetch_result(reference))
                assay = uow.troponin_evidence.assay_by_code(str(parsed["assay_code"]))
                if assay is None:
                    raise DomainInvariantError("unsupported assay definition")
                source_identity, source_revision = self._source_delivery_identity(parsed)
                duplicate = uow.troponin_evidence.source_revision(
                    job.connector_id, source_identity, source_revision
                )
                if duplicate is None:
                    supersedes_result_id = self._source_predecessor(
                        uow, job.connector_id, source_identity, source_revision, parsed
                    )
                    record = self._make_record(
                        job.clinical_case_id,
                        assay,
                        parsed,
                        actor,
                        now,
                        job.connector_id,
                        "laboratory",
                        source_identity=source_identity,
                        source_revision=source_revision,
                        supersedes_result_id=supersedes_result_id,
                    )
                    uow.troponin_evidence.session.add(record)
                    job.resulting_result_ids = [str(record.result_id)]
                    self._stage(
                        uow,
                        self._source_delivery_event(record.result_status),
                        record.result_id,
                        1,
                        job.clinical_case_id,
                        actor,
                        {
                            "case_id": str(job.clinical_case_id),
                            "result_id": str(record.result_id),
                            "import_job_id": str(job.import_job_id),
                            "source_identity": source_identity,
                            "source_revision": source_revision,
                        },
                    )
                else:
                    job.resulting_result_ids = [str(duplicate.result_id)]
                    job.warnings = ["Duplicate source delivery reused the existing result."]
                job.status = "completed_with_warning" if job.warnings else "completed"
                job.failure_category = None
                job.failure_detail_safe = None
                job.completed_at = utc_now()
            except (LaboratoryConnectorError, DomainInvariantError) as error:
                job.status = "failed"
                job.failure_category = getattr(error, "category", "validation")
                job.failure_detail_safe = str(error)[:500]
                job.completed_at = utc_now()
            self._stage(
                uow,
                "LaboratoryImportRetried.v1",
                job.import_job_id,
                job.record_version,
                job.clinical_case_id,
                actor,
                {
                    "case_id": str(job.clinical_case_id),
                    "import_job_id": str(job.import_job_id),
                    "status": job.status,
                    "retry_count": job.retry_count,
                },
            )
            response = self._job_dict(job)
            self._store(
                uow,
                actor,
                "RetryLaboratoryImport",
                idempotency_key,
                fingerprint,
                job.import_job_id,
                response,
                now,
            )
            uow.commit()
            return response

    def transition_repeat(
        self,
        request_id: UUID,
        action: str,
        expected_version: int,
        actor: ActorContext,
        idempotency_key: str,
        completed_result_id: UUID | None = None,
        reason: str | None = None,
    ) -> dict[str, object]:
        fingerprint = command_fingerprint(
            {
                "request_id": request_id,
                "action": action,
                "expected_version": expected_version,
                "completed_result_id": completed_result_id,
                "reason": reason,
            }
        )
        with self._uow_factory() as uow:
            prior = self._idempotent(
                uow, actor, f"{action.title()}RepeatTroponinRequest", idempotency_key, fingerprint
            )
            if prior:
                return dict(prior.response_payload)
            record = uow.troponin_evidence.session.get(RepeatTroponinRequestRecord, request_id)
            if record is None:
                raise ResourceNotFoundError("repeat troponin request was not found")
            if record.record_version != expected_version:
                raise ResourceConflictError("stale repeat request version")
            now = utc_now()
            if action == "acknowledge" and record.status == "requested":
                record.status = "acknowledged"
                record.acknowledged_by_actor_id = actor.actor_id
                record.acknowledged_at = now
            elif action == "complete" and record.status in {"requested", "acknowledged"}:
                if completed_result_id is None:
                    raise DomainInvariantError("completed_result_id is required")
                result = uow.troponin_evidence.session.get(
                    TroponinEvidenceRecord, completed_result_id
                )
                if result is None or result.clinical_case_id != record.clinical_case_id:
                    raise ResourceNotFoundError("completion result was not found for this case")
                source_result = uow.troponin_evidence.session.get(
                    TroponinEvidenceRecord, record.source_result_id
                )
                if (
                    source_result is None
                    or result.specimen_collected_at <= source_result.specimen_collected_at
                ):
                    raise ResourceConflictError(
                        "completion result must be a subsequent result for the same case"
                    )
                record.status = "completed"
                record.completed_result_id = completed_result_id
                record.completed_at = now
            elif action == "cancel" and record.status in {"requested", "acknowledged"}:
                record.status = "cancelled"
                record.cancellation_reason = require_text(reason or "", "cancellation_reason")
            else:
                raise ResourceConflictError("repeat request transition is not permitted")
            record.record_version += 1
            response = self._repeat_dict(record)
            event = {
                "acknowledge": "RepeatTroponinMeasurementAcknowledged.v1",
                "complete": "RepeatTroponinMeasurementCompleted.v1",
                "cancel": "RepeatTroponinMeasurementCancelled.v1",
            }[action]
            self._stage(
                uow,
                event,
                record.request_id,
                record.record_version,
                record.clinical_case_id,
                actor,
                {
                    "case_id": str(record.clinical_case_id),
                    "request_id": str(record.request_id),
                    "status": record.status,
                },
            )
            self._store(
                uow,
                actor,
                f"{action.title()}RepeatTroponinRequest",
                idempotency_key,
                fingerprint,
                record.request_id,
                response,
                now,
            )
            uow.commit()
            return response

    def _record(
        self, command: RecordTroponinResult, command_type: str, fingerprint: str
    ) -> dict[str, object]:
        with self._uow_factory() as uow:
            prior = self._idempotent(
                uow, command.actor, command_type, command.idempotency_key, fingerprint
            )
            if prior:
                return dict(prior.response_payload)
            self._case(uow, command.case_id, command.expected_case_version)
            assay = uow.troponin_evidence.assay_by_code(command.assay_code)
            if assay is None:
                raise ResourceNotFoundError("troponin assay was not found")
            data = {
                "analyte": command.analyte,
                "value": command.value,
                "unit": command.unit,
                "specimen_type": command.specimen_type,
                "specimen_collected_at": command.specimen_collected_at,
                "resulted_at": command.resulted_at,
                "status": command.result_status,
                "reference_limit": command.reference_limit_value,
                "reference_limit_unit": command.reference_limit_unit,
                "reference_limit_source": command.reference_limit_source,
                "quality_flags": list(command.quality_flags),
                "source_result_id": command.source_result_id,
                "accession_number": command.accession_number,
                "note": command.note,
            }
            record = self._make_record(
                command.case_id,
                assay,
                data,
                command.actor,
                utc_now(),
                command.source_system,
                "manual",
            )
            uow.troponin_evidence.session.add(record)
            response = self._result_dict(record, assay)
            self._stage(
                uow,
                "TroponinResultRecorded.v1",
                record.result_id,
                1,
                command.case_id,
                command.actor,
                {
                    "case_id": str(command.case_id),
                    "result_id": str(record.result_id),
                    "assay_id": str(assay.assay_id),
                },
            )
            self._store(
                uow,
                command.actor,
                command_type,
                command.idempotency_key,
                fingerprint,
                record.result_id,
                response,
                record.recorded_at,
            )
            uow.commit()
            return response

    @staticmethod
    def _source_delivery_identity(data: dict[str, object]) -> tuple[str, int]:
        identity = require_text(
            str(data.get("source_identity") or data.get("external_result_id")),
            "source_identity",
        )
        raw_revision = data.get("source_revision", 1)
        if not isinstance(raw_revision, (str, int)):
            raise DomainInvariantError("source_revision must be a positive integer")
        try:
            revision = int(raw_revision)
        except (TypeError, ValueError) as error:
            raise DomainInvariantError("source_revision must be a positive integer") from error
        if revision < 1:
            raise DomainInvariantError("source_revision must be a positive integer")
        return identity, revision

    @staticmethod
    def _source_predecessor(
        uow: UnitOfWork,
        source_system: str,
        source_identity: str,
        source_revision: int,
        data: dict[str, object],
    ) -> UUID | None:
        if source_revision == 1:
            return None
        raw_predecessor_revision = data.get("supersedes_source_revision", source_revision - 1)
        if not isinstance(raw_predecessor_revision, (str, int)):
            raise DomainInvariantError("source delivery revisions must be sequential")
        predecessor_revision = int(raw_predecessor_revision)
        if predecessor_revision != source_revision - 1:
            raise DomainInvariantError("source delivery revisions must be sequential")
        predecessor = uow.troponin_evidence.source_revision(
            source_system, source_identity, predecessor_revision
        )
        if predecessor is None:
            raise ResourceConflictError("source delivery predecessor was not received")
        return cast(UUID, predecessor.result_id)

    @staticmethod
    def _source_delivery_event(status: str) -> str:
        return {
            "preliminary": "TroponinResultPreliminaryReceived.v1",
            "final": "TroponinResultFinalized.v1",
            "amended": "TroponinResultSourceAmended.v1",
        }.get(status, "TroponinResultImported.v1")

    @staticmethod
    def _make_record(
        case_id: UUID,
        assay: TroponinAssayRecord,
        data: dict[str, object],
        actor: ActorContext,
        now: datetime,
        source_system: str,
        source_type: str,
        *,
        source_identity: str | None = None,
        source_revision: int = 1,
        supersedes_result_id: UUID | None = None,
    ) -> TroponinEvidenceRecord:
        if str(data["analyte"]) != assay.analyte:
            raise DomainInvariantError("analyte is incompatible with the selected assay")
        collected_value = data.get("specimen_collected_at")
        resulted_value = data.get("resulted_at")
        collected = require_utc(
            collected_value if isinstance(collected_value, datetime) else now,
            "specimen_collected_at",
        )
        resulted = require_utc(
            resulted_value if isinstance(resulted_value, datetime) else now,
            "resulted_at",
        )
        if resulted < collected:
            raise DomainInvariantError("result timestamp cannot precede specimen collection")
        normalized = UnitConversionPolicy.normalize(
            UnitConversionPolicy.decimal(str(data["value"])),
            str(data["unit"]),
            assay.canonical_unit,
        )
        ref = (
            UnitConversionPolicy.decimal(str(data["reference_limit"]))
            if data.get("reference_limit") not in {None, ""}
            else None
        )
        ref_unit = (
            str(data.get("reference_limit_unit")) if data.get("reference_limit_unit") else None
        )
        if (ref is None) != (ref_unit is None):
            raise DomainInvariantError("reference limit value and unit must be supplied together")
        quality_flags = data.get("quality_flags", [])
        if not isinstance(quality_flags, (list, tuple)):
            raise DomainInvariantError("quality_flags must be a list")
        return TroponinEvidenceRecord(
            result_id=uuid4(),
            clinical_case_id=case_id,
            assay_id=assay.assay_id,
            analyte=assay.analyte,
            original_value=normalized.original_value,
            original_unit=normalized.original_unit,
            normalized_value=normalized.normalized_value,
            normalized_unit=normalized.normalized_unit,
            conversion_status=normalized.conversion_status,
            conversion_version=normalized.conversion_version,
            specimen_type=require_text(
                str(data.get("specimen_type", "unspecified")), "specimen_type"
            ),
            specimen_collected_at=collected,
            resulted_at=resulted,
            result_status=ResultStatus(str(data.get("status", "unknown"))).value,
            reference_limit_value=ref,
            reference_limit_unit=ref_unit,
            reference_limit_source=str(data.get("reference_limit_source"))
            if data.get("reference_limit_source")
            else None,
            quality_flags=[str(x) for x in quality_flags],
            source_system=require_text(source_system, "source_system"),
            source_type=source_type,
            source_result_id=require_text(
                str(data.get("source_result_id") or data.get("external_result_id")),
                "source_result_id",
            ),
            source_identity=require_text(
                source_identity
                or str(
                    data.get("source_identity")
                    or data.get("external_result_id")
                    or data.get("source_result_id")
                ),
                "source_identity",
            ),
            source_revision=source_revision,
            accession_number=str(data.get("accession_number"))
            if data.get("accession_number")
            else None,
            note=str(data.get("note")) if data.get("note") else None,
            supersedes_result_id=supersedes_result_id,
            amendment_reason=(
                str(data.get("source_amendment_reason"))
                if data.get("source_amendment_reason")
                else None
            ),
            recorded_by_actor_id=actor.actor_id,
            recorded_by_role=actor.actor_role,
            recorded_at=now,
            correlation_id=actor.correlation_id,
            record_version=1,
        )

    @staticmethod
    def _case(uow: UnitOfWork, case_id: UUID, expected_version: int) -> object:
        case = uow.cases.get(case_id)
        if case is None:
            raise ResourceNotFoundError("clinical case was not found")
        if case.version != expected_version:
            raise ResourceConflictError("stale clinical case version")
        if case.status is CaseStatus.CLOSED:
            raise ResourceConflictError("troponin evidence cannot be changed after case closure")
        return case

    @staticmethod
    def _idempotent(
        uow: UnitOfWork, actor: ActorContext, command_type: str, key: str, fingerprint: str
    ) -> IdempotencyResult | None:
        existing = cast(
            IdempotencyResult | None,
            uow.idempotency.lock_and_get(
                actor.actor_id, command_type, require_text(key, "idempotency_key")
            ),
        )
        if existing and existing.request_hash != fingerprint:
            raise ResourceConflictError("idempotency key was already used with a different request")
        return existing

    @staticmethod
    def _store(
        uow: UnitOfWork,
        actor: ActorContext,
        command_type: str,
        key: str,
        fingerprint: str,
        resource_id: UUID,
        response: dict[str, object],
        now: datetime,
    ) -> None:
        uow.idempotency.add(
            IdempotencyResult(
                actor.actor_id,
                command_type,
                key,
                uuid4(),
                fingerprint,
                "TroponinEvidence",
                resource_id,
                response,
                now,
            )
        )

    @staticmethod
    def _stage(
        uow: UnitOfWork,
        event_type: str,
        aggregate_id: UUID,
        version: int,
        case_id: UUID,
        actor: ActorContext,
        payload: dict[str, object],
    ) -> None:
        uow.stage_event(
            EventEnvelope.from_context(
                event_type=event_type,
                aggregate_type="TroponinEvidence",
                aggregate_id=aggregate_id,
                aggregate_version=version,
                payload={"case_id": str(case_id), **payload},
                context=EventContext(
                    actor.correlation_id, actor.causation_id, actor.actor_id, actor.audit_metadata()
                ),
            )
        )

    @staticmethod
    def _result_dict(r: TroponinEvidenceRecord, assay: TroponinAssayRecord) -> dict[str, object]:
        return {
            "result_id": str(r.result_id),
            "clinical_case_id": str(r.clinical_case_id),
            "assay_id": str(r.assay_id),
            "assay_code": assay.code,
            "assay_display_name": assay.display_name,
            "assay_category": assay.category,
            "manufacturer": assay.manufacturer,
            "platform": assay.platform,
            "assay_version": assay.assay_version,
            "analyte": r.analyte,
            "original_value": str(r.original_value),
            "original_unit": r.original_unit,
            "normalized_value": str(r.normalized_value) if r.normalized_value is not None else None,
            "normalized_unit": r.normalized_unit,
            "conversion_status": r.conversion_status,
            "conversion_version": r.conversion_version,
            "specimen_type": r.specimen_type,
            "specimen_collected_at": r.specimen_collected_at.isoformat(),
            "resulted_at": r.resulted_at.isoformat(),
            "result_status": r.result_status,
            "reference_limit_value": str(r.reference_limit_value)
            if r.reference_limit_value is not None
            else None,
            "reference_limit_unit": r.reference_limit_unit,
            "reference_limit_source": r.reference_limit_source,
            "quality_flags": list(r.quality_flags),
            "source_system": r.source_system,
            "source_type": r.source_type,
            "source_result_id": r.source_result_id,
            "source_identity": r.source_identity,
            "source_revision": r.source_revision,
            "accession_number": r.accession_number,
            "note": r.note,
            "supersedes_result_id": str(r.supersedes_result_id) if r.supersedes_result_id else None,
            "amendment_reason": r.amendment_reason,
            "recorded_by_actor_id": str(r.recorded_by_actor_id) if r.recorded_by_actor_id else None,
            "recorded_by_role": r.recorded_by_role,
            "recorded_at": r.recorded_at.isoformat(),
            "correlation_id": str(r.correlation_id),
            "record_version": r.record_version,
        }

    @staticmethod
    def _job_dict(j: LaboratoryImportJobRecord) -> dict[str, object]:
        return {
            "import_job_id": str(j.import_job_id),
            "clinical_case_id": str(j.clinical_case_id),
            "connector_id": j.connector_id,
            "external_reference": j.external_reference,
            "status": j.status,
            "requested_at": j.requested_at.isoformat(),
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "resulting_result_ids": list(j.resulting_result_ids),
            "parser_name": j.parser_name,
            "parser_version": j.parser_version,
            "warnings": list(j.warnings),
            "failure_category": j.failure_category,
            "failure_detail_safe": j.failure_detail_safe,
            "retry_count": j.retry_count,
            "correlation_id": str(j.correlation_id),
            "record_version": j.record_version,
        }

    @staticmethod
    def _review_dict(
        r: ClinicianTroponinReviewRecord, request: RepeatTroponinRequestRecord | None = None
    ) -> dict[str, object]:
        return {
            "review_id": str(r.review_id),
            "clinical_case_id": str(r.clinical_case_id),
            "referenced_result_ids": list(r.referenced_result_ids),
            "actor_id": str(r.actor_id),
            "actor_role": r.actor_role,
            "review_status": r.review_status,
            "incompatibility_acknowledged": r.incompatibility_acknowledged,
            "quality_limitation_acknowledged": r.quality_limitation_acknowledged,
            "repeat_measurement_requested": r.repeat_measurement_requested,
            "repeat_measurement_reason": r.repeat_measurement_reason,
            "note": r.note,
            "occurred_at": r.occurred_at.isoformat(),
            "recorded_at": r.recorded_at.isoformat(),
            "correlation_id": str(r.correlation_id),
            "supersedes_review_id": str(r.supersedes_review_id) if r.supersedes_review_id else None,
            "correction_reason": r.correction_reason,
            "record_version": r.record_version,
            "repeat_request": TroponinApplicationService._repeat_dict(request) if request else None,
        }

    @staticmethod
    def _repeat_dict(r: RepeatTroponinRequestRecord) -> dict[str, object]:
        return {
            "request_id": str(r.request_id),
            "clinical_case_id": str(r.clinical_case_id),
            "source_result_id": str(r.source_result_id),
            "requested_by_actor_id": str(r.requested_by_actor_id),
            "reason": r.reason,
            "requested_at": r.requested_at.isoformat(),
            "status": r.status,
            "acknowledged_by_actor_id": str(r.acknowledged_by_actor_id)
            if r.acknowledged_by_actor_id
            else None,
            "acknowledged_at": r.acknowledged_at.isoformat() if r.acknowledged_at else None,
            "completed_result_id": str(r.completed_result_id) if r.completed_result_id else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "cancellation_reason": r.cancellation_reason,
            "correlation_id": str(r.correlation_id),
            "record_version": r.record_version,
        }


class TroponinQueryService:
    def __init__(
        self,
        uow_factory: Any,
        connectors: Mapping[str, LaboratoryResultConnector],
    ) -> None:
        self._uow_factory = uow_factory
        self._connectors = dict(connectors)

    def assays(self) -> list[dict[str, object]]:
        with self._uow_factory() as uow:
            rows = (
                uow.troponin_evidence.session.query(TroponinAssayRecord)
                .filter_by(active=True)
                .order_by(TroponinAssayRecord.display_name)
                .all()
            )
            return [self._assay(r) for r in rows]

    def assay(self, assay_id: UUID) -> dict[str, object]:
        with self._uow_factory() as uow:
            row = uow.troponin_evidence.session.get(TroponinAssayRecord, assay_id)
            if row is None:
                raise ResourceNotFoundError("troponin assay was not found")
            return self._assay(row)

    def result(self, result_id: UUID) -> dict[str, object]:
        with self._uow_factory() as uow:
            row = uow.troponin_evidence.session.get(TroponinEvidenceRecord, result_id)
            if row is None:
                raise ResourceNotFoundError("troponin result was not found")
            assay = uow.troponin_evidence.session.get(TroponinAssayRecord, row.assay_id)
            return TroponinApplicationService._result_dict(row, assay)

    def workspace(self, case_id: UUID) -> dict[str, object]:
        with self._uow_factory() as uow:
            case = uow.cases.get(case_id)
            if case is None:
                raise ResourceNotFoundError("clinical case was not found")
            history = uow.troponin_evidence.results_for_case(case_id)
            effective = uow.troponin_evidence.effective_results(case_id)
            assays = {
                r.assay_id: uow.troponin_evidence.session.get(TroponinAssayRecord, r.assay_id)
                for r in history
            }
            results = [
                TroponinApplicationService._result_dict(r, assays[r.assay_id]) for r in history
            ]
            effective_results = [
                TroponinApplicationService._result_dict(r, assays[r.assay_id]) for r in effective
            ]
            deltas = [
                self._delta(calculate_delta(a, b))
                for a, b in zip(effective, effective[1:], strict=False)
            ]
            review_records = uow.troponin_evidence.reviews(case_id)
            reviews = [TroponinApplicationService._review_dict(r) for r in review_records]
            superseded_reviews = {
                record.supersedes_review_id
                for record in review_records
                if record.supersedes_review_id is not None
            }
            latest_review = next(
                (
                    TroponinApplicationService._review_dict(record)
                    for record in reversed(review_records)
                    if record.review_id not in superseded_reviews
                ),
                None,
            )
            requests = [
                TroponinApplicationService._repeat_dict(r)
                for r in uow.troponin_evidence.repeat_requests(case_id)
            ]
            jobs = [
                TroponinApplicationService._job_dict(j)
                for j in uow.troponin_evidence.import_jobs(case_id)
            ]
            latest = effective_results[-1] if effective_results else None
            return {
                "clinical_case_id": str(case_id),
                "case_version": case.version,
                "effective_results": effective_results,
                "result_history": results,
                "latest_result": latest,
                "deltas": deltas,
                "import_jobs": jobs,
                "latest_clinician_review": latest_review,
                "clinician_reviews": reviews,
                "repeat_measurement_requests": requests,
                "data_freshness": latest["recorded_at"] if latest else None,
                "capabilities": {
                    "manual_entry": True,
                    "mock_laboratory_import": True,
                    "live_lis": False,
                    "amendment": True,
                    "clinician_review": True,
                    "repeat_measurement": True,
                },
                "safety_notice": (
                    "Numerical laboratory evidence only - clinician interpretation required. "
                    "No AMI diagnosis or disposition is produced."
                ),
            }

    def connectors(self) -> list[dict[str, object]]:
        return [
            {
                "connector_id": item.connector_id,
                "connector_type": item.connector_type,
                "capabilities": list(item.capabilities()),
                "source_info": item.source_info(),
                "live_lis": False,
            }
            for item in self._connectors.values()
        ]

    def connector_health(self, connector_id: str) -> dict[str, object]:
        connector = self._connectors.get(connector_id)
        if connector is None:
            raise ResourceNotFoundError("laboratory connector was not found")
        return {"connector_id": connector_id, **connector.health()}

    def import_job(self, job_id: UUID) -> dict[str, object]:
        with self._uow_factory() as uow:
            job = uow.troponin_evidence.session.get(LaboratoryImportJobRecord, job_id)
            if job is None:
                raise ResourceNotFoundError("laboratory import job was not found")
            return TroponinApplicationService._job_dict(job)

    @staticmethod
    def _assay(a: TroponinAssayRecord) -> dict[str, object]:
        return {
            "assay_id": str(a.assay_id),
            "code": a.code,
            "display_name": a.display_name,
            "analyte": a.analyte,
            "category": a.category,
            "manufacturer": a.manufacturer,
            "platform": a.platform,
            "assay_version": a.assay_version,
            "canonical_unit": a.canonical_unit,
            "effective_version": a.effective_version,
            "active": a.active,
        }

    @staticmethod
    def _delta(d: Any) -> dict[str, object]:
        return {
            "baseline_result_id": str(d.baseline_result_id),
            "current_result_id": str(d.current_result_id),
            "baseline_value": str(d.baseline_value),
            "current_value": str(d.current_value),
            "absolute_change": str(d.absolute_change) if d.absolute_change is not None else None,
            "relative_change_percent": str(d.relative_change_percent)
            if d.relative_change_percent is not None
            else None,
            "normalized_unit": d.normalized_unit,
            "specimen_interval_seconds": d.specimen_interval_seconds,
            "compatibility_status": d.compatibility_status.value,
            "incompatibility_reasons": list(d.incompatibility_reasons),
            "calculation_policy_version": d.calculation_policy_version,
            "warning": d.warning,
        }
