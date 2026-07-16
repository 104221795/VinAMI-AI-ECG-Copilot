"""Framework-free identity, role, permission, and scope contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from vinami.identity.domain.model import ClinicalRole
from vinami.shared.domain import DomainInvariantError, require_text, require_utc


class Permission(StrEnum):
    """Explicit application capabilities enforced at delivery boundaries."""

    PATIENT_CREATE = "patient:create"
    PATIENT_READ = "patient:read"
    ENCOUNTER_CREATE = "encounter:create"
    ENCOUNTER_READ = "encounter:read"
    CLINICAL_CASE_CREATE = "clinical_case:create"
    CLINICAL_CASE_READ = "clinical_case:read"
    COMMAND_CENTER_READ = "command_center:read"
    TRIAGE_READ = "triage:read"
    TRIAGE_WRITE = "triage:write"
    VITALS_READ = "vitals:read"
    VITALS_WRITE = "vitals:write"
    ECG_READ = "ecg:read"
    ECG_WRITE = "ecg:write"
    ECG_INTERPRET = "ecg:interpret"
    TROPONIN_READ = "troponin:read"
    TROPONIN_WRITE = "troponin:write"
    TROPONIN_REVIEW = "troponin:review"
    CLINICAL_REASONING_READ = "clinical_reasoning:read"
    CLINICAL_REASONING_WRITE = "clinical_reasoning:write"
    CLINICAL_DECISION_WRITE = "clinical_decision:write"
    WORKFLOW_READ = "workflow:read"
    TASK_WRITE = "task:write"
    ALERT_WRITE = "alert:write"
    TIMELINE_READ = "timeline:read"
    AUDIT_READ = "audit:read"
    OUTCOME_WRITE = "outcome:write"
    RESEARCH_EXPORT_CREATE = "research_export:create"
    INTEGRATION_READ = "integration:read"
    INTEGRATION_WRITE = "integration:write"
    IDENTITY_INSPECT = "identity:inspect"
    SYSTEM_READ = "system:read"


_READ_PERMISSIONS = frozenset(
    {
        Permission.PATIENT_READ,
        Permission.ENCOUNTER_READ,
        Permission.CLINICAL_CASE_READ,
        Permission.COMMAND_CENTER_READ,
        Permission.TIMELINE_READ,
        Permission.TRIAGE_READ,
        Permission.VITALS_READ,
        Permission.ECG_READ,
        Permission.TROPONIN_READ,
        Permission.CLINICAL_REASONING_READ,
        Permission.WORKFLOW_READ,
        Permission.INTEGRATION_READ,
    }
)
_MUTATION_PERMISSIONS = frozenset(
    {
        Permission.PATIENT_CREATE,
        Permission.ENCOUNTER_CREATE,
        Permission.CLINICAL_CASE_CREATE,
        Permission.TRIAGE_WRITE,
        Permission.VITALS_WRITE,
        Permission.ECG_WRITE,
        Permission.TROPONIN_WRITE,
        Permission.TASK_WRITE,
        Permission.ALERT_WRITE,
    }
)

ROLE_PERMISSIONS = MappingProxyType(
    {
        ClinicalRole.PHYSICIAN: _READ_PERMISSIONS
        | _MUTATION_PERMISSIONS
        | {
            Permission.AUDIT_READ,
            Permission.ECG_INTERPRET,
            Permission.TROPONIN_REVIEW,
            Permission.CLINICAL_REASONING_WRITE,
            Permission.CLINICAL_DECISION_WRITE,
            Permission.OUTCOME_WRITE,
            Permission.RESEARCH_EXPORT_CREATE,
            Permission.INTEGRATION_WRITE,
        },
        ClinicalRole.NURSE: _READ_PERMISSIONS | _MUTATION_PERMISSIONS,
        ClinicalRole.TECHNICIAN: _READ_PERMISSIONS | {Permission.ECG_WRITE, Permission.TASK_WRITE},
        ClinicalRole.CARE_COORDINATOR: _READ_PERMISSIONS | _MUTATION_PERMISSIONS,
        ClinicalRole.ADMINISTRATOR: frozenset(Permission),
        ClinicalRole.AUDITOR: _READ_PERMISSIONS
        | {
            Permission.AUDIT_READ,
            Permission.IDENTITY_INSPECT,
            Permission.RESEARCH_EXPORT_CREATE,
            Permission.INTEGRATION_READ,
            Permission.SYSTEM_READ,
        },
        ClinicalRole.SYSTEM_SERVICE: frozenset(Permission),
        ClinicalRole.READ_ONLY_REVIEWER: _READ_PERMISSIONS,
        ClinicalRole.COORDINATOR: _READ_PERMISSIONS | _MUTATION_PERMISSIONS,
        ClinicalRole.SYSTEM: frozenset(Permission),
    }
)


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    """Identity claims accepted only after provider verification."""

    subject_id: str
    actor_id: UUID
    display_name: str
    roles: frozenset[ClinicalRole]
    permissions: frozenset[Permission]
    organization: str | None
    location_scope: tuple[str, ...]
    authentication_method: str
    identity_provider: str
    issued_at: datetime
    expires_at: datetime
    session_reference: str | None = None
    email: str | None = None
    directory_reference: str | None = None
    claims_reference: str | None = None

    def __post_init__(self) -> None:
        """Validate safe, normalized identity provenance without retaining credentials."""
        if self.actor_id.int == 0:
            raise DomainInvariantError("verified actor_id must not be the nil UUID")
        if not self.roles:
            raise DomainInvariantError("verified identity must contain at least one role")
        object.__setattr__(self, "subject_id", require_text(self.subject_id, "subject_id"))
        object.__setattr__(self, "display_name", require_text(self.display_name, "display_name"))
        object.__setattr__(
            self,
            "authentication_method",
            require_text(self.authentication_method, "authentication_method"),
        )
        object.__setattr__(
            self, "identity_provider", require_text(self.identity_provider, "identity_provider")
        )
        object.__setattr__(self, "issued_at", require_utc(self.issued_at, "issued_at"))
        object.__setattr__(self, "expires_at", require_utc(self.expires_at, "expires_at"))
        if self.expires_at <= self.issued_at:
            raise DomainInvariantError("identity expiration must follow issue time")

    @property
    def primary_role(self) -> ClinicalRole:
        """Return a deterministic persisted role for legacy aggregate authorization checks."""
        return sorted(self.roles, key=lambda role: role.value)[0]


@dataclass(frozen=True, slots=True)
class ResourceContext:
    """Optional resource ownership facts for future organization and team enforcement."""

    organization: str | None = None
    location: str | None = None
    assigned_team_id: UUID | None = None
