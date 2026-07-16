"""Shared HTTP contracts and authenticated command-context factories."""

from dataclasses import dataclass
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from vinami.audit.domain.model import AuditEntry
from vinami.identity.domain.security import Permission, VerifiedIdentity
from vinami.identity.ports.errors import AuthenticationFailedError, AuthorizationDeniedError
from vinami.identity.ports.provider import AuthenticationRequest
from vinami.shared.actor import ActorContext
from vinami.shared.application_errors import ActorContextError
from vinami.shared.container import AppContainer
from vinami.shared.domain import require_text, utc_now

_BEARER = HTTPBearer(auto_error=False)


class ProblemDetail(BaseModel):
    """RFC 7807-compatible error document with request correlation."""

    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    instance: str
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class AuthorizedIdentity:
    """Verified identity paired with the permission applied to this operation."""

    identity: VerifiedIdentity
    permission: Permission

    def actor_context(self, request: Request) -> ActorContext:
        """Construct authoritative application provenance from verified claims."""
        correlation_id = UUID(str(request.state.correlation_id))
        return ActorContext(
            actor_id=self.identity.actor_id,
            actor_role=self.identity.primary_role.value,
            correlation_id=correlation_id,
            request_source=_request_source(request),
            identity_subject=self.identity.subject_id,
            actor_roles=tuple(sorted(role.value for role in self.identity.roles)),
            applied_permission=self.permission.value,
            identity_provider=self.identity.identity_provider,
            authentication_method=self.identity.authentication_method,
            session_reference=self.identity.session_reference,
        )


@dataclass(frozen=True, slots=True)
class CommandHeaders:
    """Authenticated actor provenance plus persistent idempotency metadata."""

    actor: ActorContext
    idempotency_key: str
    visible_locations: tuple[str, ...]


def authenticate_request(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_BEARER)],
    development_identity: Annotated[
        str | None,
        Header(
            alias="X-Development-Identity",
            description="Configured synthetic identity key; development mode only",
        ),
    ] = None,
) -> VerifiedIdentity:
    """Authenticate through the configured provider and bind its stable actor reference."""
    container = _container(request)
    try:
        identity = container.identity_provider.authenticate(
            AuthenticationRequest(
                access_token=credentials.credentials if credentials is not None else None,
                development_identity=development_identity,
            )
        )
        container.identity_binding.bind(identity)
    except AuthenticationFailedError:
        audit_request_outcome(request, "authentication_failure", "security:authenticate")
        raise
    request.state.verified_identity = identity
    return identity


def authorize_for(permission: Permission) -> Any:
    """Create a FastAPI dependency that delegates one explicit permission to the policy port."""

    def authorize(
        request: Request,
        identity: Annotated[VerifiedIdentity, Depends(authenticate_request)],
    ) -> AuthorizedIdentity:
        container = _container(request)
        try:
            container.authorization_policy.require_permission(identity, permission)
        except AuthorizationDeniedError:
            request.state.verified_identity = identity
            request.state.applied_permission = permission
            audit_request_outcome(request, "authorization_failure", "security:authorize")
            raise
        authorized = AuthorizedIdentity(identity, permission)
        request.state.authorized_identity = authorized
        request.state.applied_permission = permission
        return authorized

    return authorize


def command_headers_for(permission: Permission) -> Any:
    """Create an authenticated command dependency for one explicit capability."""
    authorization_dependency = authorize_for(permission)

    def command_headers(
        request: Request,
        authorized: Annotated[AuthorizedIdentity, Depends(authorization_dependency)],
        idempotency_key: Annotated[
            str | None,
            Header(alias="Idempotency-Key", description="Persistent command deduplication key"),
        ] = None,
    ) -> CommandHeaders:
        if idempotency_key is None:
            raise ActorContextError("Idempotency-Key is required")
        return CommandHeaders(
            actor=authorized.actor_context(request),
            idempotency_key=require_text(idempotency_key, "idempotency_key"),
            visible_locations=tuple(authorized.identity.location_scope),
        )

    return command_headers


def audit_request_outcome(request: Request, outcome: str, action: str) -> None:
    """Append a credential-free request security/rejection audit record."""
    container = _container(request)
    identity = cast(VerifiedIdentity | None, getattr(request.state, "verified_identity", None))
    permission = cast(Permission | None, getattr(request.state, "applied_permission", None))
    correlation_id = UUID(str(request.state.correlation_id))
    resource_id = UUID(bytes=correlation_id.bytes)
    container.audit_writer().append(
        AuditEntry(
            case_id=None,
            aggregate_type="HttpRequest",
            aggregate_id=resource_id,
            action=action,
            occurred_at=utc_now(),
            actor_id=identity.actor_id if identity is not None else None,
            actor_role=identity.primary_role.value if identity is not None else None,
            identity_subject=identity.subject_id if identity is not None else None,
            actor_roles=(
                tuple(sorted(role.value for role in identity.roles)) if identity is not None else ()
            ),
            applied_permission=permission.value if permission is not None else None,
            identity_provider=identity.identity_provider if identity is not None else None,
            authentication_method=(
                identity.authentication_method if identity is not None else None
            ),
            session_reference=identity.session_reference if identity is not None else None,
            prior_version=None,
            resulting_version=None,
            reason=None,
            correlation_id=correlation_id,
            causation_id=None,
            outcome=outcome,
            request_source=_request_source(request),
            payload={"method": request.method, "path": request.url.path},
        )
    )


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


def _request_source(request: Request) -> str:
    source = request.headers.get("X-Request-Source", "api").strip()
    if not source or len(source) > 160:
        return "api"
    return source
