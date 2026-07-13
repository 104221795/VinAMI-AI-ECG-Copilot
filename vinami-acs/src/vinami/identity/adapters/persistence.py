"""SQLAlchemy mappings for the minimal clinical actor and team placeholder."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from vinami.identity.domain.model import ClinicalRole
from vinami.shared.persistence import Base, JSONDocument, UUIDType


class ClinicalTeamRecord(Base):
    """Persisted task-assignment team reference."""

    __tablename__ = "clinical_teams"

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)


class ClinicalUserRecord(Base):
    """Persisted actor reference without credentials or external identity integration."""

    __tablename__ = "clinical_users"
    __table_args__ = (
        UniqueConstraint(
            "identity_provider", "identity_subject", name="uq_clinical_user_provider_subject"
        ),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[ClinicalRole] = mapped_column(
        Enum(ClinicalRole, name="clinical_role"), nullable=False
    )
    team_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_teams.id", ondelete="SET NULL"), nullable=True
    )
    identity_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    identity_provider: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authentication_method: Mapped[str | None] = mapped_column(String(80), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(200), nullable=True)
    location_scope: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False, default=list)
