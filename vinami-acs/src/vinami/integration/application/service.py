"""R10 simulated hospital integration processing through validated backend commands."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from vinami.ecg.adapters.ingestion import build_demo_waveform
from vinami.ecg.application.service import ECGApplicationService, IngestECG
from vinami.ecg.domain.clinical import ECGSourceType
from vinami.integration.adapters.persistence import (
    IntegrationMessageRecord,
    message_from_record,
)
from vinami.integration.domain.model import IntegrationMessage, IntegrationMessageStatus
from vinami.shared.actor import ActorContext
from vinami.shared.application_errors import ResourceConflictError, ResourceNotFoundError
from vinami.shared.domain import DomainInvariantError, require_text, require_utc, utc_now
from vinami.shared.events.contracts import EventEnvelope
from vinami.troponin.adapters.r4_persistence import TroponinEvidenceRecord
from vinami.troponin.application.service import RecordTroponinResult, TroponinApplicationService

MAX_RETRIES = 3


class UnitOfWork(Protocol):
    integration_messages: Any
    cases: Any
    troponin_evidence: Any

    def __enter__(self) -> UnitOfWork: ...
    def __exit__(self, *args: object) -> None: ...
    def stage_event(self, event: EventEnvelope) -> None: ...
    def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class SimulatedLabMessage:
    """Validated delivery DTO for a local HL7/FHIR-shaped troponin result."""

    external_message_id: str
    source_system: str
    schema_version: str
    clinical_case_id: UUID
    assay_code: str
    analyte: str
    value: str
    unit: str
    specimen_type: str
    specimen_collected_at: datetime
    resulted_at: datetime
    result_status: str
    source_result_id: str
    expected_case_version: int
    reference_limit_value: str | None = None
    reference_limit_unit: str | None = None
    reference_limit_source: str | None = None
    quality_flags: tuple[str, ...] = ()
    accession_number: str | None = None
    note: str | None = None
    amendment_of_message_id: str | None = None
    amendment_reason: str | None = None
    failure_mode: str | None = None


@dataclass(frozen=True, slots=True)
class SimulatedECGMessage:
    """Validated delivery DTO for a deterministic local ECG device message."""

    external_message_id: str
    source_system: str
    schema_version: str
    clinical_case_id: UUID
    study_reference: str
    acquisition_at: datetime
    expected_case_version: int
    poor_quality: bool = False
    failure_mode: str | None = None


class IntegrationApplicationService:
    """Validate and import simulated hospital messages without direct clinical authority."""

    def __init__(
        self,
        uow_factory: Any,
        troponin_application: TroponinApplicationService,
        ecg_application: ECGApplicationService,
    ) -> None:
        self._uow_factory = uow_factory
        self._troponin = troponin_application
        self._ecg = ecg_application

    def receive_lab_result(
        self, message: SimulatedLabMessage, actor: ActorContext, idempotency_key: str
    ) -> IntegrationMessage:
        """Process a simulated laboratory message through troponin commands."""
        payload = _payload(message)
        existing = self._existing_message(message.source_system, message.external_message_id)
        if existing is not None:
            return existing
        record = self._create_record(
            message.external_message_id,
            message.source_system,
            "lab_result_amendment" if message.amendment_of_message_id else "lab_result",
            message.schema_version,
            message.clinical_case_id,
            payload,
            actor,
        )
        validation_errors = self._validate_common(record)
        if message.failure_mode == "temporary":
            return self._mark_retry(record, actor, "temporary simulated LIS outage")
        if validation_errors:
            return self._mark_failed(record, actor, validation_errors, permanent=True)
        if message.amendment_of_message_id:
            return self._process_lab_amendment(record, message, actor, idempotency_key)
        return self._process_lab_result(record, message, actor, idempotency_key)

    def receive_ecg_study(
        self, message: SimulatedECGMessage, actor: ActorContext, idempotency_key: str
    ) -> IntegrationMessage:
        """Process a simulated ECG-device message through the ECG ingestion command."""
        payload = _payload(message)
        existing = self._existing_message(message.source_system, message.external_message_id)
        if existing is not None:
            return existing
        record = self._create_record(
            message.external_message_id,
            message.source_system,
            "ecg_study",
            message.schema_version,
            message.clinical_case_id,
            payload,
            actor,
        )
        validation_errors = self._validate_common(record)
        if message.failure_mode == "temporary":
            return self._mark_retry(record, actor, "temporary simulated ECG-device outage")
        if validation_errors:
            return self._mark_failed(record, actor, validation_errors, permanent=True)
        return self._process_ecg_study(record, message, actor, idempotency_key)

    def retry_message(
        self, message_id: UUID, actor: ActorContext, idempotency_key: str
    ) -> IntegrationMessage:
        """Retry a pending or dead-letter simulated message using its persisted payload."""
        with self._uow_factory() as uow:
            record = uow.integration_messages.get(message_id)
            if record is None:
                raise ResourceNotFoundError("integration message was not found")
            if record.status not in {
                IntegrationMessageStatus.RETRY_PENDING.value,
                IntegrationMessageStatus.FAILED.value,
                IntegrationMessageStatus.DEAD_LETTER.value,
            }:
                raise ResourceConflictError("integration message is not retryable")
            record.retry_count += 1
            record.record_version += 1
            record.status = IntegrationMessageStatus.RECEIVED.value
            record.last_error = None
            record.dead_letter_reason = None
            record.validation_errors = []
            uow.commit()
        payload = dict(record.payload)
        payload["failure_mode"] = None
        if record.message_type == "ecg_study":
            ecg_message = _ecg_message(payload)
            validation_errors = self._validate_common(record)
            if validation_errors:
                return self._mark_failed(record, actor, validation_errors, permanent=True)
            return self._process_ecg_study(record, ecg_message, actor, idempotency_key)
        lab_message = _lab_message(payload)
        validation_errors = self._validate_common(record)
        if validation_errors:
            return self._mark_failed(record, actor, validation_errors, permanent=True)
        if lab_message.amendment_of_message_id:
            return self._process_lab_amendment(record, lab_message, actor, idempotency_key)
        return self._process_lab_result(record, lab_message, actor, idempotency_key)

    def list_messages(
        self, *, status: str | None = None, source_system: str | None = None, limit: int = 50
    ) -> list[IntegrationMessage]:
        """Return recent integration ledger rows for operational monitoring."""
        with self._uow_factory() as uow:
            return [
                message_from_record(item)
                for item in uow.integration_messages.latest(
                    status=status, source_system=source_system, limit=limit
                )
            ]

    def _existing_message(
        self, source_system: str, external_message_id: str
    ) -> IntegrationMessage | None:
        with self._uow_factory() as uow:
            record = uow.integration_messages.by_external_id(source_system, external_message_id)
            return message_from_record(record) if record is not None else None

    def _create_record(
        self,
        external_message_id: str,
        source_system: str,
        message_type: str,
        schema_version: str,
        case_id: UUID,
        payload: dict[str, object],
        actor: ActorContext,
    ) -> IntegrationMessageRecord:
        now = utc_now()
        record = IntegrationMessageRecord(
            message_id=uuid4(),
            external_message_id=require_text(external_message_id, "external_message_id"),
            source_system=require_text(source_system, "source_system"),
            message_type=message_type,
            schema_version=require_text(schema_version, "schema_version"),
            clinical_case_id=case_id,
            received_at=now,
            processed_at=None,
            status=IntegrationMessageStatus.RECEIVED.value,
            correlation_id=actor.correlation_id,
            causation_id=actor.causation_id,
            retry_count=0,
            validation_errors=[],
            linked_record_ids=[],
            payload=payload,
            checksum_sha256=_checksum(payload),
            simulated=True,
            record_version=1,
        )
        with self._uow_factory() as uow:
            uow.integration_messages.add(record)
            uow.stage_event(_integration_event("IntegrationMessageReceived.v1", record, actor))
            uow.commit()
        return record

    def _validate_common(self, record: IntegrationMessageRecord) -> list[str]:
        errors: list[str] = []
        if not record.clinical_case_id:
            errors.append("clinical_case_id is required")
        if not record.schema_version.startswith("vinami-"):
            errors.append("unsupported simulated schema profile")
        return errors

    def _process_lab_result(
        self,
        record: IntegrationMessageRecord,
        message: SimulatedLabMessage,
        actor: ActorContext,
        idempotency_key: str,
    ) -> IntegrationMessage:
        try:
            result = self._troponin.record_result(
                RecordTroponinResult(
                    case_id=message.clinical_case_id,
                    assay_code=message.assay_code,
                    analyte=message.analyte,
                    value=message.value,
                    unit=message.unit,
                    specimen_type=message.specimen_type,
                    specimen_collected_at=message.specimen_collected_at,
                    resulted_at=message.resulted_at,
                    result_status=message.result_status,
                    reference_limit_value=message.reference_limit_value,
                    reference_limit_unit=message.reference_limit_unit,
                    reference_limit_source=message.reference_limit_source,
                    quality_flags=message.quality_flags,
                    source_system=message.source_system,
                    source_result_id=message.source_result_id,
                    accession_number=message.accession_number,
                    note=message.note,
                    expected_case_version=message.expected_case_version,
                    actor=actor,
                    idempotency_key=idempotency_key,
                )
            )
        except (
            DomainInvariantError,
            ResourceConflictError,
            ResourceNotFoundError,
            ValueError,
        ) as error:
            return self._mark_failed(record, actor, [str(error)], permanent=False)
        return self._mark_processed(record, actor, [str(result["result_id"])])

    def _process_ecg_study(
        self,
        record: IntegrationMessageRecord,
        message: SimulatedECGMessage,
        actor: ActorContext,
        idempotency_key: str,
    ) -> IntegrationMessage:
        try:
            job, study = self._ecg.ingest(
                IngestECG(
                    actor=actor,
                    idempotency_key=idempotency_key,
                    clinical_case_id=message.clinical_case_id,
                    source_type=ECGSourceType.CANONICAL_WAVEFORM,
                    study_reference=message.study_reference,
                    acquisition_at=message.acquisition_at,
                    content=build_demo_waveform(poor_quality=message.poor_quality),
                    content_type="application/vnd.vinami.ecg+json",
                    original_filename=f"{message.study_reference}.json",
                    source_connector_id=message.source_system,
                    external_reference=message.external_message_id,
                    expected_case_version=message.expected_case_version,
                )
            )
        except (
            DomainInvariantError,
            ResourceConflictError,
            ResourceNotFoundError,
            ValueError,
        ) as error:
            return self._mark_failed(record, actor, [str(error)], permanent=False)
        linked = [str(job.id)]
        if study is not None:
            linked.append(str(study.study_id))
        return self._mark_processed(record, actor, linked)

    def _process_lab_amendment(
        self,
        record: IntegrationMessageRecord,
        message: SimulatedLabMessage,
        actor: ActorContext,
        idempotency_key: str,
    ) -> IntegrationMessage:
        if not message.amendment_of_message_id:
            return self._mark_failed(record, actor, ["amendment predecessor is required"], True)
        with self._uow_factory() as uow:
            predecessor = uow.integration_messages.by_external_id(
                message.source_system, message.amendment_of_message_id
            )
            if predecessor is None or not predecessor.linked_record_ids:
                return self._mark_failed(
                    record,
                    actor,
                    ["amendment predecessor has not been processed"],
                    permanent=True,
                )
            result_id = UUID(str(predecessor.linked_record_ids[-1]))
            result = uow.troponin_evidence.session.get(TroponinEvidenceRecord, result_id)
            if result is None:
                raise ResourceNotFoundError("amended troponin result was not found")
            expected_version = result.record_version
        try:
            amended = self._troponin.amend_result(
                result_id,
                value=message.value,
                unit=message.unit,
                status=message.result_status,
                reason=message.amendment_reason or "Simulated laboratory amendment.",
                resulted_at=message.resulted_at,
                expected_version=expected_version,
                actor=actor,
                idempotency_key=idempotency_key,
            )
        except (
            DomainInvariantError,
            ResourceConflictError,
            ResourceNotFoundError,
            ValueError,
        ) as error:
            return self._mark_failed(record, actor, [str(error)], permanent=False)
        return self._mark_processed(record, actor, [str(amended["result_id"])])

    def _mark_processed(
        self, record: IntegrationMessageRecord, actor: ActorContext, linked_ids: list[str]
    ) -> IntegrationMessage:
        with self._uow_factory() as uow:
            stored = uow.integration_messages.get(record.message_id)
            if stored is None:
                raise ResourceNotFoundError("integration message was not found")
            stored.status = IntegrationMessageStatus.PROCESSED.value
            stored.processed_at = utc_now()
            stored.linked_record_ids = linked_ids
            stored.record_version += 1
            uow.stage_event(_integration_event("IntegrationMessageProcessed.v1", stored, actor))
            uow.commit()
            return message_from_record(stored)

    def _mark_retry(
        self, record: IntegrationMessageRecord, actor: ActorContext, reason: str
    ) -> IntegrationMessage:
        with self._uow_factory() as uow:
            stored = uow.integration_messages.get(record.message_id)
            if stored is None:
                raise ResourceNotFoundError("integration message was not found")
            stored.retry_count += 1
            stored.last_error = reason
            stored.validation_errors = [reason]
            stored.status = (
                IntegrationMessageStatus.DEAD_LETTER.value
                if stored.retry_count >= MAX_RETRIES
                else IntegrationMessageStatus.RETRY_PENDING.value
            )
            stored.dead_letter_reason = reason if stored.status == "dead_letter" else None
            stored.processed_at = utc_now()
            stored.record_version += 1
            uow.stage_event(_integration_event("IntegrationMessageFailed.v1", stored, actor))
            uow.commit()
            return message_from_record(stored)

    def _mark_failed(
        self,
        record: IntegrationMessageRecord,
        actor: ActorContext,
        errors: list[str],
        permanent: bool,
    ) -> IntegrationMessage:
        with self._uow_factory() as uow:
            stored = uow.integration_messages.get(record.message_id)
            if stored is None:
                raise ResourceNotFoundError("integration message was not found")
            stored.retry_count += 1
            stored.validation_errors = errors
            stored.last_error = "; ".join(errors)[:4000]
            stored.status = (
                IntegrationMessageStatus.DEAD_LETTER.value
                if permanent or stored.retry_count >= MAX_RETRIES
                else IntegrationMessageStatus.FAILED.value
            )
            stored.dead_letter_reason = (
                stored.last_error if stored.status == "dead_letter" else None
            )
            stored.processed_at = utc_now()
            stored.record_version += 1
            uow.stage_event(_integration_event("IntegrationMessageFailed.v1", stored, actor))
            uow.commit()
            return message_from_record(stored)


def _payload(message: SimulatedLabMessage | SimulatedECGMessage) -> dict[str, object]:
    document = asdict(message)
    payload = {
        key: _json(value)
        for key, value in document.items()
        if value is not None and key != "failure_mode"
    }
    if document.get("failure_mode"):
        payload["failure_mode"] = str(document["failure_mode"])
    return payload


def _json(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, tuple):
        return list(value)
    return value


def _checksum(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _integration_event(
    event_type: str, record: IntegrationMessageRecord, actor: ActorContext
) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        aggregate_type="IntegrationMessage",
        aggregate_id=record.message_id,
        aggregate_version=record.record_version,
        actor_id=actor.actor_id,
        correlation_id=actor.correlation_id,
        causation_id=actor.causation_id,
        occurred_at=record.processed_at or record.received_at,
        payload={
            "message_id": str(record.message_id),
            "case_id": str(record.clinical_case_id) if record.clinical_case_id else None,
            "external_message_id": record.external_message_id,
            "source_system": record.source_system,
            "message_type": record.message_type,
            "status": record.status,
            "linked_record_ids": record.linked_record_ids,
            "validation_errors": record.validation_errors,
        },
        metadata={**actor.audit_metadata(), "simulated_source": record.simulated},
    )


def _lab_message(payload: dict[str, object]) -> SimulatedLabMessage:
    return SimulatedLabMessage(
        external_message_id=str(payload["external_message_id"]),
        source_system=str(payload["source_system"]),
        schema_version=str(payload["schema_version"]),
        clinical_case_id=UUID(str(payload["clinical_case_id"])),
        assay_code=str(payload["assay_code"]),
        analyte=str(payload["analyte"]),
        value=str(payload["value"]),
        unit=str(payload["unit"]),
        specimen_type=str(payload["specimen_type"]),
        specimen_collected_at=require_utc(
            datetime.fromisoformat(str(payload["specimen_collected_at"])),
            "specimen_collected_at",
        ),
        resulted_at=require_utc(datetime.fromisoformat(str(payload["resulted_at"])), "resulted_at"),
        result_status=str(payload["result_status"]),
        source_result_id=str(payload["source_result_id"]),
        expected_case_version=int(str(payload["expected_case_version"])),
        reference_limit_value=_optional(payload.get("reference_limit_value")),
        reference_limit_unit=_optional(payload.get("reference_limit_unit")),
        reference_limit_source=_optional(payload.get("reference_limit_source")),
        quality_flags=_string_tuple(payload.get("quality_flags", ())),
        accession_number=_optional(payload.get("accession_number")),
        note=_optional(payload.get("note")),
        amendment_of_message_id=_optional(payload.get("amendment_of_message_id")),
        amendment_reason=_optional(payload.get("amendment_reason")),
        failure_mode=_optional(payload.get("failure_mode")),
    )


def _ecg_message(payload: dict[str, object]) -> SimulatedECGMessage:
    return SimulatedECGMessage(
        external_message_id=str(payload["external_message_id"]),
        source_system=str(payload["source_system"]),
        schema_version=str(payload["schema_version"]),
        clinical_case_id=UUID(str(payload["clinical_case_id"])),
        study_reference=str(payload["study_reference"]),
        acquisition_at=require_utc(
            datetime.fromisoformat(str(payload["acquisition_at"])), "acquisition_at"
        ),
        expected_case_version=int(str(payload["expected_case_version"])),
        poor_quality=bool(payload.get("poor_quality", False)),
        failure_mode=_optional(payload.get("failure_mode")),
    )


def _optional(value: object) -> str | None:
    return str(value) if value is not None else None


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return ()
