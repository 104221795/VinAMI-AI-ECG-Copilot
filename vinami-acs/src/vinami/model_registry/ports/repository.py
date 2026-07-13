"""Persistence port for registered model metadata."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from vinami.model_registry.domain.model import ModelRegistryEntry


class ModelRegistryRepository(Protocol):
    """Persist immutable name/version model provenance records."""

    def add(self, entry: ModelRegistryEntry) -> None:
        """Stage a model entry."""

    def get(self, entry_id: UUID) -> ModelRegistryEntry | None:
        """Return a model entry by UUID."""
