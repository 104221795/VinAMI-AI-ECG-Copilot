"""Framework-free persistent idempotency contracts for application commands."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


def command_fingerprint(payload: dict[str, Any]) -> str:
    """Return a stable SHA-256 digest for one normalized command payload."""
    document = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class IdempotencyResult:
    """Stored successful command result scoped to actor, command type, and key."""

    actor_id: UUID
    command_type: str
    idempotency_key: str
    command_id: UUID
    request_hash: str
    resource_type: str
    resource_id: UUID
    response_payload: dict[str, Any]
    created_at: datetime


class IdempotencyRepository(Protocol):
    """Serialize and persist command deduplication inside the active transaction."""

    def lock_and_get(
        self, actor_id: UUID, command_type: str, idempotency_key: str
    ) -> IdempotencyResult | None:
        """Lock one idempotency scope and return its stored result when present."""

    def add(self, result: IdempotencyResult) -> None:
        """Stage a successful command result in the same aggregate transaction."""
