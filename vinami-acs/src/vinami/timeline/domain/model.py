"""Immutable timeline event value object."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from vinami.shared.domain import require_text, require_utc


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    """A projected chronological event that never mutates its source aggregate."""

    case_id: UUID
    event_type: str
    occurred_at: datetime
    payload: dict[str, Any]
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Validate event identity and UTC ordering information."""
        object.__setattr__(self, "event_type", require_text(self.event_type, "timeline event type"))
        object.__setattr__(self, "occurred_at", require_utc(self.occurred_at, "occurred_at"))
