"""API-independent serial-troponin commands and explicitly non-clinical demo timing policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from vinami.shared.domain import DomainInvariantError, require_utc
from vinami.troponin.domain.model import (
    TroponinAssay,
    TroponinMeasurement,
    TroponinQualityFlag,
    TroponinTimeline,
)

DEMO_NOTICE = "Demonstration rule - not for clinical use."


@dataclass(frozen=True, slots=True)
class DemoTroponinTimingPolicy:
    """Versioned synthetic timing policy; it is not a clinical threshold or guideline."""

    version: str
    expected_interval_minutes: int
    repeated_reminder_minutes: int
    notice: str = DEMO_NOTICE

    def __post_init__(self) -> None:
        if (
            self.notice != DEMO_NOTICE
            or self.expected_interval_minutes <= 0
            or self.repeated_reminder_minutes <= 0
        ):
            raise DomainInvariantError("invalid demonstration troponin timing policy")


@dataclass(frozen=True, slots=True)
class OrderTroponin:
    case_id: UUID
    order_reference: str
    ordered_at: datetime


@dataclass(frozen=True, slots=True)
class RecordTroponinCollection:
    case_id: UUID
    order_reference: str
    collected_at: datetime


@dataclass(frozen=True, slots=True)
class RecordTroponinResult:
    case_id: UUID
    order_reference: str
    assay: TroponinAssay
    raw_value: float
    collected_at: datetime
    resulted_at: datetime
    quality_flags: tuple[TroponinQualityFlag, ...] = ()
    renal_function_context: str | None = None
    source_system: str = "unspecified"
    source_record_id: str | None = None
    ingested_at: datetime | None = None
    reference_metadata: tuple[tuple[str, str], ...] = ()

    def measurement(self) -> TroponinMeasurement:
        return TroponinMeasurement(
            uuid4(),
            self.raw_value,
            self.assay,
            self.collected_at,
            self.resulted_at,
            self.order_reference,
            self.quality_flags,
            self.renal_function_context,
            self.source_system,
            self.source_record_id,
            self.ingested_at,
            self.reference_metadata,
        )


def apply_order(timeline: TroponinTimeline, command: OrderTroponin) -> None:
    if timeline.case_id != command.case_id:
        raise DomainInvariantError("troponin timeline does not belong to command case")
    timeline.order(command.order_reference, require_utc(command.ordered_at, "ordered_at"))


def apply_collection(timeline: TroponinTimeline, command: RecordTroponinCollection) -> None:
    if timeline.case_id != command.case_id:
        raise DomainInvariantError("troponin timeline does not belong to command case")
    timeline.collect(command.order_reference, require_utc(command.collected_at, "collected_at"))


def apply_result(timeline: TroponinTimeline, command: RecordTroponinResult) -> TroponinMeasurement:
    if timeline.case_id != command.case_id:
        raise DomainInvariantError("troponin timeline does not belong to command case")
    measurement = command.measurement()
    timeline.record_result(measurement)
    return measurement
