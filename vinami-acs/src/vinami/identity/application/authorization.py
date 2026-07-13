"""Permission and minimal resource-scope authorization policy."""

from __future__ import annotations

from vinami.identity.domain.security import Permission, ResourceContext, VerifiedIdentity
from vinami.identity.ports.errors import AuthorizationDeniedError


class ExplicitAuthorizationPolicy:
    """Enforce verified permissions and an optional organization/location scope."""

    def require_permission(
        self,
        identity: VerifiedIdentity,
        permission: Permission,
        resource_context: ResourceContext | None = None,
    ) -> None:
        """Reject missing capabilities and explicit scope mismatches."""
        if not self.can(identity, permission, resource_context):
            raise AuthorizationDeniedError("the verified identity is not permitted to act")

    def can(
        self,
        identity: VerifiedIdentity,
        permission: Permission,
        resource_context: ResourceContext | None = None,
    ) -> bool:
        """Evaluate explicit permission and currently available resource scope facts."""
        if permission not in identity.permissions:
            return False
        if resource_context is None:
            return True
        if (
            resource_context.organization is not None
            and identity.organization is not None
            and resource_context.organization != identity.organization
        ):
            return False
        return not (
            resource_context.location is not None
            and identity.location_scope
            and resource_context.location not in identity.location_scope
        )
