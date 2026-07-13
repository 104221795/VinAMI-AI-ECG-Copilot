"""Framework-free tests for versioned event envelope serialization."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from vinami.shared.events.contracts import EventContext, EventEnvelope
from vinami.shared.events.registry import EventRegistry, UnsupportedEventVersionError
from vinami.shared.events.serializer import EventSerializer


def test_serializer_round_trip_preserves_version_and_provenance() -> None:
    """A durable document retains correlation, causation, actor, and metadata fields."""
    serializer = EventSerializer(EventRegistry.default())
    correlation_id = uuid4()
    causation_id = uuid4()
    actor_id = uuid4()
    event = EventEnvelope.from_context(
        event_type="ClinicalCaseOpened.v1",
        aggregate_type="ClinicalCase",
        aggregate_id=uuid4(),
        aggregate_version=1,
        payload={"case_id": "case-1"},
        context=EventContext(
            correlation_id=correlation_id,
            causation_id=causation_id,
            actor_id=actor_id,
            metadata={"source": "unit-test"},
        ),
    )

    restored = serializer.deserialize(serializer.serialize(event))

    assert restored.event_id == event.event_id
    assert restored.event_version == 1
    assert restored.correlation_id == correlation_id
    assert restored.causation_id == causation_id
    assert restored.actor_id == actor_id
    assert restored.metadata == {"source": "unit-test"}


def test_serializer_rejects_unknown_schema_version() -> None:
    """Dispatcher cannot silently consume a payload contract it does not understand."""
    serializer = EventSerializer(EventRegistry.default())
    event = EventEnvelope(
        event_type="ClinicalCaseOpened.v1",
        event_version=2,
        aggregate_type="ClinicalCase",
        aggregate_id=uuid4(),
        aggregate_version=1,
        occurred_at=datetime(2026, 7, 13, tzinfo=UTC),
        payload={},
    )

    with pytest.raises(UnsupportedEventVersionError):
        serializer.serialize(event)
