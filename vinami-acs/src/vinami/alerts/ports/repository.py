"""Persistence port for safety alert lifecycle operations."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from vinami.alerts.domain.model import Alert


class AlertRepository(Protocol):
    """Persist and retrieve review alerts without clinical inference."""

    def add(self, alert: Alert) -> None:
        """Stage a newly raised alert."""

    def get(self, alert_id: UUID) -> Alert | None:
        """Return an alert by UUID."""

    def save(self, alert: Alert) -> None:
        """Persist acknowledgement or resolution provenance."""

    def list_by_case(self, case_id: UUID) -> list[Alert]:
        """Return all alerts owned by one clinical case."""

    def get_by_deduplication_key(self, key: str) -> Alert | None:
        """Find an alert by deterministic operational condition key."""
