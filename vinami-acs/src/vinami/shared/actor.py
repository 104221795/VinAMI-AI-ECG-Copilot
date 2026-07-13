"""Framework-free actor context required by consequential application commands."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from vinami.shared.domain import DomainInvariantError, require_text

PHYSICIAN_ROLES = frozenset({"physician"})


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Structurally authenticated actor provenance without implementing authentication."""

    actor_id: UUID
    actor_role: str
    correlation_id: UUID
    causation_id: UUID | None = None

    def __post_init__(self) -> None:
        """Require a real actor identifier, explicit role, and correlation identifier."""
        if self.actor_id.int == 0:
            raise DomainInvariantError("actor_id must not be the nil UUID")
        if self.correlation_id.int == 0:
            raise DomainInvariantError("correlation_id must not be the nil UUID")
        object.__setattr__(self, "actor_role", require_text(self.actor_role, "actor_role"))

    @classmethod
    def for_actor(
        cls,
        actor_id: UUID,
        actor_role: str,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> ActorContext:
        """Create context while allowing a delivery adapter to omit only correlation creation."""
        return cls(actor_id, actor_role, correlation_id or uuid4(), causation_id)

    def require_physician(self) -> None:
        """Reject a consequential clinical decision from a non-physician role."""
        if self.actor_role not in PHYSICIAN_ROLES:
            raise DomainInvariantError(
                f"actor role {self.actor_role!r} is not authorized for physician decisions"
            )
