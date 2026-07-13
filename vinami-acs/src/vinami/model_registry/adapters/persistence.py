"""SQLAlchemy mapping and repository for model registry entries."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, Session, mapped_column

from vinami.model_registry.domain.model import ModelRegistryEntry, ModelStatus
from vinami.shared.persistence import Base, UTCDateTime, UUIDType


class ModelRegistryRecord(Base):
    """Model identity and immutable provenance metadata, not a loaded model artifact."""

    __tablename__ = "model_registry"
    __table_args__ = (
        UniqueConstraint("model_name", "model_version", name="uq_model_registry_name_version"),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)
    input_contract: Mapped[str] = mapped_column(String(1000), nullable=False)
    artifact_digest: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[ModelStatus] = mapped_column(
        Enum(ModelStatus, name="model_status"), nullable=False, index=True
    )
    registered_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    validation_reference: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class SQLAlchemyModelRegistryRepository:
    """Model registry repository without model-runtime dependencies."""

    def __init__(self, session: Session) -> None:
        """Bind repository work to one transaction session."""
        self._session = session

    def add(self, entry: ModelRegistryEntry) -> None:
        """Insert one unique model name/version entry."""
        self._session.add(
            ModelRegistryRecord(
                id=entry.id,
                model_name=entry.model_name,
                model_version=entry.model_version,
                input_contract=entry.input_contract,
                artifact_digest=entry.artifact_digest,
                status=entry.status,
                registered_at=entry.registered_at,
                validation_reference=entry.validation_reference,
            )
        )

    def get(self, entry_id: UUID) -> ModelRegistryEntry | None:
        """Rehydrate a registry entry by UUID."""
        record = self._session.get(ModelRegistryRecord, entry_id)
        if record is None:
            return None
        return ModelRegistryEntry(
            id=record.id,
            model_name=record.model_name,
            model_version=record.model_version,
            input_contract=record.input_contract,
            artifact_digest=record.artifact_digest,
            status=record.status,
            registered_at=record.registered_at,
            validation_reference=record.validation_reference,
        )
