"""Framework-free actor context required by application commands."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from vinami.shared.domain import DomainInvariantError, require_text

PHYSICIAN_ROLES = frozenset({"physician"})


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Application actor provenance constructed from a verified identity at API boundaries."""

    actor_id: UUID
    actor_role: str
    correlation_id: UUID
    causation_id: UUID | None = None
    request_source: str = "internal"
    identity_subject: str | None = None
    actor_roles: tuple[str, ...] = ()
    applied_permission: str | None = None
    identity_provider: str | None = None
    authentication_method: str | None = None
    session_reference: str | None = None

    def __post_init__(self) -> None:
        """Require a real actor identifier, explicit role, and correlation identifier."""
        if self.actor_id.int == 0:
            raise DomainInvariantError("actor_id must not be the nil UUID")
        if self.correlation_id.int == 0:
            raise DomainInvariantError("correlation_id must not be the nil UUID")
        object.__setattr__(self, "actor_role", require_text(self.actor_role, "actor_role"))
        object.__setattr__(
            self, "request_source", require_text(self.request_source, "request_source")
        )
        if not self.actor_roles:
            object.__setattr__(self, "actor_roles", (self.actor_role,))

    @classmethod
    def for_actor(
        cls,
        actor_id: UUID,
        actor_role: str,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        request_source: str = "internal",
    ) -> ActorContext:
        """Create context while allowing a delivery adapter to omit only correlation creation."""
        return cls(actor_id, actor_role, correlation_id or uuid4(), causation_id, request_source)

    def require_physician(self) -> None:
        """Reject a consequential clinical decision from a non-physician role."""
        if self.actor_role not in PHYSICIAN_ROLES:
            raise DomainInvariantError(
                f"actor role {self.actor_role!r} is not authorized for physician decisions"
            )

    def audit_metadata(self) -> dict[str, object]:
        """Return safe identity provenance for events and audit; credentials are never present."""
        return {
            "actor_role": self.actor_role,
            "actor_roles": list(self.actor_roles),
            "request_source": self.request_source,
            "identity_subject": self.identity_subject,
            "applied_permission": self.applied_permission,
            "identity_provider": self.identity_provider,
            "authentication_method": self.authentication_method,
            "session_reference": self.session_reference,
        }
