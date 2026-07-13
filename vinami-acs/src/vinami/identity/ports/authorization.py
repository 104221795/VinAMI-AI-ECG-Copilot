"""Application authorization-policy port."""

from __future__ import annotations

from typing import Protocol

from vinami.identity.domain.security import Permission, ResourceContext, VerifiedIdentity


class AuthorizationPolicy(Protocol):
    """Evaluate explicit capabilities without coupling callers to role mappings."""

    def require_permission(
        self,
        identity: VerifiedIdentity,
        permission: Permission,
        resource_context: ResourceContext | None = None,
    ) -> None:
        """Raise when the verified identity cannot perform the operation."""

    def can(
        self,
        identity: VerifiedIdentity,
        permission: Permission,
        resource_context: ResourceContext | None = None,
    ) -> bool:
        """Return whether an identity has permission within the supplied scope."""
