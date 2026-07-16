"""Framework-independent R4 troponin laboratory evidence contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from vinami.shared.domain import DomainInvariantError, require_text, require_utc


class AssayCategory(StrEnum):
    HS_CTNI = "hs_ctni"
    HS_CTNT = "hs_ctnt"
    CONVENTIONAL_CTNI = "conventional_ctni"
    CONVENTIONAL_CTNT = "conventional_ctnt"
    UNKNOWN = "unknown"


class ResultStatus(StrEnum):
    PRELIMINARY = "preliminary"
    FINAL = "final"
    AMENDED = "amended"
    CORRECTED = "corrected"
    CANCELLED = "cancelled"
    ENTERED_IN_ERROR = "entered_in_error"
    UNKNOWN = "unknown"


class CompatibilityStatus(StrEnum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE_ASSAY = "incompatible_assay"
    INCOMPATIBLE_ANALYTE = "incompatible_analyte"
    NORMALIZATION_UNAVAILABLE = "normalization_unavailable"


class ImportStatus(StrEnum):
    REQUESTED = "requested"
    RECEIVING = "receiving"
    VALIDATING = "validating"
    PARSING = "parsing"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNING = "completed_with_warning"
    REJECTED = "rejected"
    FAILED = "failed"


class RepeatRequestStatus(StrEnum):
    REQUESTED = "requested"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class AssayDefinition:
    assay_id: UUID
    code: str
    display_name: str
    analyte: str
    category: AssayCategory
    manufacturer: str
    platform: str
    assay_version: str
    canonical_unit: str | None
    effective_version: int

    def __post_init__(self) -> None:
        for field_name in (
            "code",
            "display_name",
            "analyte",
            "manufacturer",
            "platform",
            "assay_version",
        ):
            object.__setattr__(
                self, field_name, require_text(getattr(self, field_name), field_name)
            )
        if self.canonical_unit is not None:
            object.__setattr__(
                self, "canonical_unit", require_text(self.canonical_unit, "canonical_unit")
            )
        if self.effective_version < 1:
            raise DomainInvariantError("effective_version must be positive")


@dataclass(frozen=True, slots=True)
class NormalizedMeasurement:
    original_value: Decimal
    original_unit: str
    normalized_value: Decimal | None
    normalized_unit: str | None
    conversion_status: str
    conversion_version: str


@dataclass(frozen=True, slots=True)
class DeltaResult:
    baseline_result_id: UUID
    current_result_id: UUID
    baseline_value: Decimal
    current_value: Decimal
    absolute_change: Decimal | None
    relative_change_percent: Decimal | None
    normalized_unit: str | None
    specimen_interval_seconds: int
    compatibility_status: CompatibilityStatus
    incompatibility_reasons: tuple[str, ...]
    calculation_policy_version: str = "troponin-delta-v1"
    warning: str = "Numerical troponin change - clinician interpretation required."


class TroponinUnitValidationError(DomainInvariantError):
    """A safe, field-specific unit validation failure for the HTTP boundary."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.field = "unit"


class UnitConversionPolicy:
    """Allow only verified dimensional conversions; never infer an assay reference limit."""

    version = "troponin-unit-conversion-v1"
    _FACTORS: dict[tuple[str, str], Decimal] = {
        ("ng/L", "ng/L"): Decimal("1"),
        ("pg/mL", "ng/L"): Decimal("1"),
        ("ng/mL", "ng/L"): Decimal("1000"),
    }

    @classmethod
    def normalize(
        cls, value: Decimal, unit: str, canonical_unit: str | None
    ) -> NormalizedMeasurement:
        if not value.is_finite() or value < 0:
            raise DomainInvariantError("troponin value must be a finite non-negative decimal")
        if not isinstance(unit, str) or not unit.strip():
            raise TroponinUnitValidationError("unit_required", "A result unit is required.")
        original_unit = unit.strip()
        if canonical_unit is None:
            return NormalizedMeasurement(
                value, original_unit, None, None, "unavailable_unknown_assay", cls.version
            )
        factor = cls._FACTORS.get((original_unit, canonical_unit))
        if factor is None:
            raise TroponinUnitValidationError(
                "unsupported_unit",
                f"unsupported troponin unit conversion: {original_unit} to {canonical_unit}.",
            )
        return NormalizedMeasurement(
            value,
            original_unit,
            value * factor,
            canonical_unit,
            "converted" if factor != 1 else "identity",
            cls.version,
        )

    @staticmethod
    def decimal(value: str | Decimal) -> Decimal:
        try:
            parsed = Decimal(value)
        except (InvalidOperation, ValueError) as error:
            raise DomainInvariantError("value must be a valid decimal") from error
        if not parsed.is_finite() or parsed < 0:
            raise DomainInvariantError("troponin value must be a finite non-negative decimal")
        return parsed


class DeltaMeasurement(Protocol):
    result_id: UUID
    assay_id: UUID
    analyte: str
    original_value: Decimal
    normalized_value: Decimal | None
    normalized_unit: str | None
    specimen_collected_at: datetime


def calculate_delta(earlier: DeltaMeasurement, later: DeltaMeasurement) -> DeltaResult:
    """Calculate a neutral numerical delta for compatible result snapshots."""
    first_time = require_utc(earlier.specimen_collected_at, "specimen_collected_at")
    second_time = require_utc(later.specimen_collected_at, "specimen_collected_at")
    if second_time < first_time:
        raise DomainInvariantError("later specimen timestamp cannot precede baseline")
    reasons: list[str] = []
    status = CompatibilityStatus.COMPATIBLE
    if earlier.analyte != later.analyte:
        status = CompatibilityStatus.INCOMPATIBLE_ANALYTE
        reasons.append("Analytes differ")
    elif earlier.assay_id != later.assay_id:
        status = CompatibilityStatus.INCOMPATIBLE_ASSAY
        reasons.append("Assay definitions differ")
    first = earlier.normalized_value
    second = later.normalized_value
    unit = earlier.normalized_unit
    if first is None or second is None or unit != later.normalized_unit:
        status = CompatibilityStatus.NORMALIZATION_UNAVAILABLE
        reasons.append("Compatible normalized values are unavailable")
    absolute = (
        second - first
        if status is CompatibilityStatus.COMPATIBLE and first is not None and second is not None
        else None
    )
    relative = None
    if absolute is not None and first is not None and first != 0:
        relative = (absolute / first) * Decimal("100")
    if absolute is not None and first == 0:
        reasons.append("Relative change is undefined for a zero baseline")
    return DeltaResult(
        baseline_result_id=earlier.result_id,
        current_result_id=later.result_id,
        baseline_value=earlier.original_value,
        current_value=later.original_value,
        absolute_change=absolute,
        relative_change_percent=relative,
        normalized_unit=unit if status is CompatibilityStatus.COMPATIBLE else None,
        specimen_interval_seconds=int((second_time - first_time).total_seconds()),
        compatibility_status=status,
        incompatibility_reasons=tuple(reasons),
    )
