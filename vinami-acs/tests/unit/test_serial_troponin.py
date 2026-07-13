"""Domain tests for serial-troponin invariants and transparent delta output."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from vinami.shared.domain import DomainInvariantError
from vinami.troponin.domain.model import TroponinAssay, TroponinMeasurement, TroponinTimeline

NOW = datetime(2026, 7, 13, 0, 0, tzinfo=UTC)


def _measurement(
    order: str, value: float, assay: TroponinAssay, minutes: int = 0
) -> TroponinMeasurement:
    return TroponinMeasurement(
        uuid4(),
        value,
        assay,
        NOW + timedelta(minutes=minutes),
        NOW + timedelta(minutes=minutes + 1),
        order,
    )


def test_rejects_unit_mismatch_for_serial_delta() -> None:
    timeline = TroponinTimeline.create(uuid4())
    first, second = (
        TroponinAssay("demo", "ng/L", reference_limit=10),
        TroponinAssay("demo", "pg/mL", reference_limit=10),
    )
    timeline.order("one")
    timeline.collect("one", NOW)
    timeline.record_result(_measurement("one", 10, first))
    timeline.order("two")
    timeline.collect("two", NOW + timedelta(minutes=1))
    timeline.record_result(_measurement("two", 20, second, 1))
    with pytest.raises(DomainInvariantError, match="same assay"):
        timeline.calculate_latest_delta("demo-v1")


def test_rejects_out_of_order_result_timestamp_and_duplicate_result() -> None:
    assay = TroponinAssay("demo", "ng/L", reference_limit=10)
    with pytest.raises(DomainInvariantError, match="cannot precede"):
        TroponinMeasurement(uuid4(), 1, assay, NOW, NOW - timedelta(seconds=1), "one")
    timeline = TroponinTimeline.create(uuid4())
    timeline.order("one")
    timeline.collect("one", NOW)
    measurement = _measurement("one", 1, assay)
    timeline.record_result(measurement)
    with pytest.raises(DomainInvariantError, match="already exists"):
        timeline.record_result(measurement)


def test_missing_baseline_and_delta_ratio_are_explicit() -> None:
    assay = TroponinAssay("demo", "ng/L", manufacturer="demo", analyzer="demo", reference_limit=10)
    timeline = TroponinTimeline.create(uuid4())
    timeline.order("one")
    timeline.collect("one", NOW)
    timeline.record_result(_measurement("one", 10, assay))
    with pytest.raises(DomainInvariantError, match="two troponin"):
        timeline.calculate_latest_delta("demo-v1")
    timeline.order("two")
    timeline.collect("two", NOW + timedelta(minutes=1))
    timeline.record_result(_measurement("two", 15, assay, 1))
    delta = timeline.calculate_latest_delta("demo-v1")
    assert (
        delta.value == 5
        and delta.relative_value == 0.5
        and timeline.measurements[-1].normalized_ratio == 1.5
    )
