"""Append-only audit writer port for accepted and rejected application commands."""

from __future__ import annotations

from typing import Protocol

from vinami.audit.domain.model import AuditEntry


class AuditWriter(Protocol):
    """Persist immutable command audit evidence without update or delete methods."""

    def append(self, entry: AuditEntry) -> None:
        """Append one audit record and case timeline item when a case is known."""
