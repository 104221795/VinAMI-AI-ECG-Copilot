"""Troponin timeline aggregate with explicit assay and temporal invariants."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from vinami.shared.domain import (
    AggregateRoot,
    DomainInvariantError,
    require_text,
    require_utc,
    utc_now,
)


@dataclass(frozen=True, slots=True)
class TroponinAssay:
    """Assay identity and result unit needed for transparent comparison."""

    name: str
    unit: str
    manufacturer: str = "unspecified"
    analyzer: str = "unspecified"
    reference_limit: float = 1.0

    def __post_init__(self) -> None:
        """Require explicit assay and unit text."""
        object.__setattr__(self, "name", require_text(self.name, "assay name"))
        object.__setattr__(self, "unit", require_text(self.unit, "assay unit"))
        object.__setattr__(self, "manufacturer", require_text(self.manufacturer, "manufacturer"))
        object.__setattr__(self, "analyzer", require_text(self.analyzer, "analyzer"))
        if self.reference_limit <= 0:
            raise DomainInvariantError("reference_limit must be positive")


class TroponinQualityFlag(StrEnum):
    """Non-diagnostic laboratory quality context attached to a result."""

    NONE = "none"
    HEMOLYSIS_REPORTED = "hemolysis_reported"
    SAMPLE_DELAYED = "sample_delayed"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True, slots=True)
class TroponinMeasurement:
    """A resulted quantitative measurement linked to its collection provenance."""

    id: UUID
    value: float
    assay: TroponinAssay
    collected_at: datetime
    resulted_at: datetime
    order_reference: str
    quality_flags: tuple[TroponinQualityFlag, ...] = ()
    renal_function_context: str | None = None
    source_system: str = "unspecified"
    source_record_id: str | None = None
    ingested_at: datetime | None = None
    reference_metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        """Reject negative values and impossible timestamp orderings."""
        if self.value < 0:
            raise DomainInvariantError("troponin value cannot be negative")
        object.__setattr__(self, "collected_at", require_utc(self.collected_at, "collected_at"))
        object.__setattr__(self, "resulted_at", require_utc(self.resulted_at, "resulted_at"))
        if self.resulted_at < self.collected_at:
            raise DomainInvariantError("resulted_at cannot precede collected_at")
        object.__setattr__(
            self, "order_reference", require_text(self.order_reference, "order_reference")
        )
        object.__setattr__(self, "source_system", require_text(self.source_system, "source_system"))
        if self.source_record_id is not None:
            object.__setattr__(
                self,
                "source_record_id",
                require_text(self.source_record_id, "source_record_id"),
            )
        if self.ingested_at is not None:
            object.__setattr__(self, "ingested_at", require_utc(self.ingested_at, "ingested_at"))
        if self.renal_function_context is not None:
            object.__setattr__(
                self,
                "renal_function_context",
                require_text(self.renal_function_context, "renal_function_context"),
            )
        object.__setattr__(self, "reference_metadata", tuple(self.reference_metadata))

    @property
    def normalized_ratio(self) -> float:
        """Return raw value divided by the assay reference limit without clinical interpretation."""
        return self.value / self.assay.reference_limit


@dataclass(frozen=True, slots=True)
class TroponinDelta:
    """Transparent absolute delta between two results from the same assay."""

    earlier_measurement_id: UUID
    later_measurement_id: UUID
    value: float
    relative_value: float | None
    calculation_version: str


@dataclass(slots=True)
class TroponinTimeline(AggregateRoot):
    """Case-owned ordered, collected, and resulted troponin evidence."""

    case_id: UUID
    measurements: list[TroponinMeasurement] = field(default_factory=list)
    ordered_references: set[str] = field(default_factory=set)
    collected_references: set[str] = field(default_factory=set)
    ordered_at_by_reference: dict[str, datetime] = field(default_factory=dict)
    collected_at_by_reference: dict[str, datetime] = field(default_factory=dict)

    @classmethod
    def create(cls, case_id: UUID, timeline_id: UUID | None = None) -> TroponinTimeline:
        """Create an empty timeline for one case."""
        return cls(id=timeline_id or uuid4(), case_id=case_id)

    def order(self, order_reference: str, ordered_at: datetime | None = None) -> None:
        """Record a unique laboratory order reference."""
        reference = require_text(order_reference, "order_reference")
        if reference in self.ordered_references:
            raise DomainInvariantError("troponin order reference already exists")
        ordered = require_utc(ordered_at or utc_now(), "ordered_at")
        self.ordered_references.add(reference)
        self.ordered_at_by_reference[reference] = ordered
        self._record_event(
            "TroponinOrdered.v1",
            1,
            {
                "case_id": str(self.case_id),
                "order_reference": reference,
                "ordered_at": ordered.isoformat(),
            },
        )

    def collect(self, order_reference: str, collected_at: datetime | None = None) -> None:
        """Record collection only for an existing order."""
        reference = require_text(order_reference, "order_reference")
        if reference not in self.ordered_references:
            raise DomainInvariantError("troponin collection requires an existing order")
        if reference in self.collected_references:
            raise DomainInvariantError("troponin order is already collected")
        collected = require_utc(collected_at or utc_now(), "collected_at")
        self.collected_references.add(reference)
        self.collected_at_by_reference[reference] = collected
        self._record_event(
            "TroponinCollected.v1",
            1,
            {
                "case_id": str(self.case_id),
                "order_reference": reference,
                "collected_at": collected.isoformat(),
            },
        )

    def record_result(self, measurement: TroponinMeasurement) -> None:
        """Record a result only once and only after collection."""
        if measurement.order_reference not in self.collected_references:
            raise DomainInvariantError("troponin result requires a collected order")
        if any(item.id == measurement.id for item in self.measurements):
            raise DomainInvariantError("troponin measurement already exists")
        self.measurements.append(measurement)
        self.measurements.sort(key=lambda item: item.collected_at)
        self._record_event(
            "TroponinResulted.v1",
            1,
            {
                "case_id": str(self.case_id),
                "measurement_id": str(measurement.id),
                "unit": measurement.assay.unit,
            },
        )

    def calculate_latest_delta(self, calculation_version: str) -> TroponinDelta:
        """Calculate an absolute delta from the last two comparable results only."""
        if len(self.measurements) < 2:
            raise DomainInvariantError("two troponin measurements are required for a delta")
        earlier, later = self.measurements[-2:]
        if earlier.assay != later.assay:
            raise DomainInvariantError("troponin delta requires measurements from the same assay")
        return TroponinDelta(
            earlier_measurement_id=earlier.id,
            later_measurement_id=later.id,
            value=later.value - earlier.value,
            relative_value=(later.value - earlier.value) / earlier.value if earlier.value else None,
            calculation_version=require_text(calculation_version, "calculation_version"),
        )
