"""JSON-safe serializer for durable event envelopes."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from vinami.shared.events.contracts import EventEnvelope
from vinami.shared.events.registry import EventRegistry


class EventSerializer:
    """Serialize and validate event envelopes independently of PostgreSQL or a future broker."""

    def __init__(self, registry: EventRegistry) -> None:
        """Receive the injected schema registry used during deserialization."""
        self._registry = registry

    def serialize(self, event: EventEnvelope) -> dict[str, Any]:
        """Return a JSON-safe dictionary with all envelope provenance fields."""
        self._registry.ensure_supported(event.event_type, event.event_version)
        return {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "event_version": event.event_version,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": str(event.aggregate_id),
            "aggregate_version": event.aggregate_version,
            "occurred_at": event.occurred_at.isoformat(),
            "correlation_id": str(event.correlation_id),
            "causation_id": str(event.causation_id) if event.causation_id else None,
            "actor_id": str(event.actor_id) if event.actor_id else None,
            "payload": _json_value(event.payload),
            "metadata": _json_value(event.metadata),
        }

    def deserialize(self, document: dict[str, Any]) -> EventEnvelope:
        """Rebuild an envelope only after validating its registered schema version."""
        event_type = _required_text(document, "event_type")
        event_version = _required_int(document, "event_version")
        self._registry.ensure_supported(event_type, event_version)
        payload = document.get("payload")
        metadata = document.get("metadata")
        if not isinstance(payload, dict) or not isinstance(metadata, dict):
            raise ValueError("event payload and metadata must be objects")
        return EventEnvelope(
            event_id=_uuid(document, "event_id"),
            event_type=event_type,
            event_version=event_version,
            aggregate_type=_required_text(document, "aggregate_type"),
            aggregate_id=_uuid(document, "aggregate_id"),
            aggregate_version=_required_int(document, "aggregate_version"),
            occurred_at=_datetime(document, "occurred_at"),
            correlation_id=_uuid(document, "correlation_id"),
            causation_id=_optional_uuid(document, "causation_id"),
            actor_id=_optional_uuid(document, "actor_id"),
            payload=payload,
            metadata=metadata,
        )


def _json_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _required_text(document: dict[str, Any], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _required_int(document: dict[str, Any], field: str) -> int:
    value = document.get(field)
    if not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _uuid(document: dict[str, Any], field: str) -> UUID:
    return UUID(_required_text(document, field))


def _optional_uuid(document: dict[str, Any], field: str) -> UUID | None:
    value = document.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a UUID string or null")
    return UUID(value)


def _datetime(document: dict[str, Any], field: str) -> datetime:
    return datetime.fromisoformat(_required_text(document, field))
