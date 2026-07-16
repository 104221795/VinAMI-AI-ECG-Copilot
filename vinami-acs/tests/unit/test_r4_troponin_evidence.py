"""Focused R4 domain and deterministic laboratory connector tests."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from vinami.shared.domain import DomainInvariantError
from vinami.troponin.adapters.laboratory import MockLaboratoryConnector
from vinami.troponin.domain.evidence import (
    CompatibilityStatus,
    UnitConversionPolicy,
    calculate_delta,
)
from vinami.troponin.ports.laboratory import (
    LaboratoryPayloadError,
    LaboratoryTimeoutError,
    LaboratoryUnavailableError,
)


@dataclass(frozen=True)
class Result:
    result_id: UUID
    assay_id: UUID
    analyte: str
    original_value: Decimal
    normalized_value: Decimal | None
    normalized_unit: str | None
    specimen_collected_at: datetime


def result(value: str, *, assay_id: UUID, minute: int) -> Result:
    return Result(
        uuid4(),
        assay_id,
        "cardiac_troponin_i",
        Decimal(value),
        Decimal(value),
        "ng/L",
        datetime(2026, 7, 14, 10, minute, tzinfo=UTC),
    )


def test_decimal_conversion_preserves_precision_and_verified_factors() -> None:
    identity = UnitConversionPolicy.normalize(Decimal("12.3400000001"), "ng/L", "ng/L")
    converted = UnitConversionPolicy.normalize(Decimal("0.01234"), "ng/mL", "ng/L")
    assert identity.normalized_value == Decimal("12.3400000001")
    assert converted.normalized_value == Decimal("12.34000")
    with pytest.raises(DomainInvariantError, match="unsupported"):
        UnitConversionPolicy.normalize(Decimal("1"), "mg/dL", "ng/L")


def test_delta_is_neutral_and_zero_baseline_has_no_relative_change() -> None:
    assay = uuid4()
    delta = calculate_delta(
        result("0", assay_id=assay, minute=0), result("4.5", assay_id=assay, minute=30)
    )
    assert delta.absolute_change == Decimal("4.5")
    assert delta.relative_change_percent is None
    assert "zero baseline" in delta.incompatibility_reasons[0]
    assert "clinician interpretation required" in delta.warning


def test_different_assays_are_not_compared() -> None:
    delta = calculate_delta(
        result("10", assay_id=uuid4(), minute=0), result("20", assay_id=uuid4(), minute=30)
    )
    assert delta.compatibility_status is CompatibilityStatus.INCOMPATIBLE_ASSAY
    assert delta.absolute_change is None


@pytest.mark.parametrize(
    ("reference", "error"),
    [
        ("unavailable", LaboratoryUnavailableError),
        ("timeout", LaboratoryTimeoutError),
        ("malformed", LaboratoryPayloadError),
    ],
)
def test_mock_connector_failure_modes_are_deterministic(
    reference: str, error: type[Exception]
) -> None:
    with pytest.raises(error):
        MockLaboratoryConnector().fetch_result(reference)


def test_mock_connector_is_explicitly_local_and_reports_missing_metadata() -> None:
    connector = MockLaboratoryConnector()
    assert connector.health()["live_lis"] is False
    payload = connector.fetch_result("missing-reference-limit")
    assert "reference_limit" not in payload
    with pytest.raises(LaboratoryPayloadError, match="unit"):
        connector.parse_result(connector.fetch_result("missing-unit"))


def test_troponin_domain_has_no_workflow_or_ai_authority() -> None:
    source = __import__("inspect").getsource(
        __import__("vinami.troponin.domain.evidence", fromlist=["*"])
    )
    for prohibited in ("vinami.workflow", "vinami.reasoning", "torch", "cath_lab"):
        assert prohibited not in source
