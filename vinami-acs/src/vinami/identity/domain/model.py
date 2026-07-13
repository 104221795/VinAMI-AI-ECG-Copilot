"""Minimal typed identity references for persistence and audit provenance."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4

from vinami.shared.domain import require_text


class ClinicalRole(StrEnum):
    """Clinical platform roles mapped from a verified external identity."""

    PHYSICIAN = "physician"
    NURSE = "nurse"
    TECHNICIAN = "technician"
    CARE_COORDINATOR = "care_coordinator"
    ADMINISTRATOR = "administrator"
    AUDITOR = "auditor"
    SYSTEM_SERVICE = "system_service"
    READ_ONLY_REVIEWER = "read_only_reviewer"

    # Retained for persisted pre-R1.5 actor references only.
    COORDINATOR = "coordinator"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class ClinicalUser:
    """Persistable clinical actor reference without credentials or identity-provider coupling."""

    display_name: str
    role: ClinicalRole
    team_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Require a human-readable audit label."""
        object.__setattr__(self, "display_name", require_text(self.display_name, "display_name"))


@dataclass(frozen=True, slots=True)
class ClinicalTeam:
    """Minimal team reference used for task assignment."""

    name: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Reject blank team names."""
        object.__setattr__(self, "name", require_text(self.name, "team name"))
