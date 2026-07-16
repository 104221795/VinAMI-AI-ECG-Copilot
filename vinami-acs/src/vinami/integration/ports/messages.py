"""Ports for inbound hospital-message processing."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from vinami.integration.domain.model import IntegrationMessage


class IntegrationMessageRepository(Protocol):
    """Persistence port for the inbound message ledger."""

    def get(self, message_id: UUID) -> object | None:
        """Return a persistence record for retry and inspection."""
        ...

    def by_external_id(self, source_system: str, external_message_id: str) -> object | None:
        """Return the durable idempotency match for an external delivery."""
        ...

    def latest(
        self, *, status: str | None = None, source_system: str | None = None, limit: int = 50
    ) -> list[object]:
        """Return recent messages for operational integration status."""
        ...


class IntegrationQueryPort(Protocol):
    """Read-side port used by API adapters."""

    def list_messages(
        self, *, status: str | None = None, source_system: str | None = None, limit: int = 50
    ) -> list[IntegrationMessage]:
        """List recent message status without exposing raw credentials or PHI."""
        ...
