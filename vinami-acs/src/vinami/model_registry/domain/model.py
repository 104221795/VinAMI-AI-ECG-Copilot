"""Model registry aggregate for immutable ECG model provenance metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from vinami.shared.domain import (
    AggregateRoot,
    DomainInvariantError,
    require_text,
    require_utc,
    utc_now,
)


class ModelStatus(StrEnum):
    """Administrative registry lifecycle, separate from any clinical decision."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    RETIRED = "retired"


@dataclass(slots=True)
class ModelRegistryEntry(AggregateRoot):
    """Immutable identity/version record for a replaceable AI provider artifact."""

    model_name: str
    model_version: str
    input_contract: str
    artifact_digest: str
    status: ModelStatus
    registered_at: datetime
    validation_reference: str | None = None

    @classmethod
    def register(
        cls,
        model_name: str,
        model_version: str,
        input_contract: str,
        artifact_digest: str,
        registered_at: datetime | None = None,
        entry_id: UUID | None = None,
        validation_reference: str | None = None,
    ) -> ModelRegistryEntry:
        """Register a model version as a candidate without importing model runtime code."""
        return cls(
            id=entry_id or uuid4(),
            model_name=require_text(model_name, "model_name"),
            model_version=require_text(model_version, "model_version"),
            input_contract=require_text(input_contract, "input_contract"),
            artifact_digest=require_text(artifact_digest, "artifact_digest"),
            status=ModelStatus.CANDIDATE,
            registered_at=require_utc(registered_at or utc_now(), "registered_at"),
            validation_reference=validation_reference,
        )

    def activate(self) -> None:
        """Mark a registered model active; inference adapter selection remains external."""
        if self.status is not ModelStatus.CANDIDATE:
            raise DomainInvariantError("only a candidate model can be activated")
        self.status = ModelStatus.ACTIVE
