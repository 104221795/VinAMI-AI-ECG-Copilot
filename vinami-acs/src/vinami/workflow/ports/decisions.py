"""Ports for immutable physician-decision persistence and actor authorization."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from vinami.workflow.domain.decision import PhysicianDecision


class PhysicianDecisionRepository(Protocol):
    """Append and retrieve immutable physician decisions."""

    def add(self, decision: PhysicianDecision) -> None:
        """Persist a new decision and make it queryable in the current transaction."""

    def get(self, decision_id: UUID) -> PhysicianDecision | None:
        """Return a decision by identifier."""

    def is_effective(self, decision_id: UUID) -> bool:
        """Return false for a revoked decision or one superseded by a revocation record."""


class ActorAuthorizationRepository(Protocol):
    """Resolve the stored role for a structurally identified clinical actor."""

    def role_for(self, actor_id: UUID) -> str | None:
        """Return the persisted actor role, or None when the actor is unknown."""
