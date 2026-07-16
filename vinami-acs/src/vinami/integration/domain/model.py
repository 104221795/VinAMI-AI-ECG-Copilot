"""Inbound integration message domain objects and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from vinami.shared.domain import DomainInvariantError, require_text, require_utc


class IntegrationMessageStatus(StrEnum):
    """Durable state of one inbound external message."""

    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    RETRY_PENDING = "retry_pending"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class IntegrationMessageType(StrEnum):
    """Supported simulated hospital integration profiles."""

    LAB_RESULT = "lab_result"
    LAB_RESULT_AMENDMENT = "lab_result_amendment"
    ECG_STUDY = "ecg_study"


@dataclass(frozen=True, slots=True)
class IntegrationMessage:
    """Safe read model for one inbound message ledger row."""

    message_id: UUID
    external_message_id: str
    source_system: str
    message_type: str
    schema_version: str
    clinical_case_id: UUID | None
    received_at: datetime
    processed_at: datetime | None
    status: str
    correlation_id: UUID
    causation_id: UUID | None
    retry_count: int
    validation_errors: tuple[str, ...]
    linked_record_ids: tuple[str, ...]
    payload: dict[str, object]
    dead_letter_reason: str | None
    simulated: bool
    record_version: int

    def __post_init__(self) -> None:
        """Require structural provenance without interpreting clinical values."""
        object.__setattr__(
            self,
            "external_message_id",
            require_text(self.external_message_id, "external_message_id"),
        )
        object.__setattr__(self, "source_system", require_text(self.source_system, "source_system"))
        object.__setattr__(self, "message_type", require_text(self.message_type, "message_type"))
        object.__setattr__(
            self, "schema_version", require_text(self.schema_version, "schema_version")
        )
        object.__setattr__(self, "received_at", require_utc(self.received_at, "received_at"))
        if self.processed_at is not None:
            object.__setattr__(self, "processed_at", require_utc(self.processed_at, "processed_at"))
        if self.retry_count < 0:
            raise DomainInvariantError("retry_count cannot be negative")
        if self.record_version < 1:
            raise DomainInvariantError("record_version must be positive")
