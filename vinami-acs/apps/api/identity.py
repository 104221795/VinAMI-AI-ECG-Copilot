"""Authenticated identity-session contract for API clients."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from apps.api.http import authenticate_request
from vinami.identity.domain.security import VerifiedIdentity
from vinami.shared.container import AppContainer


class IdentitySessionResponse(BaseModel):
    """Credential-free facts about the identity verified for this request."""

    model_config = ConfigDict(extra="forbid")

    actor_id: UUID
    subject_id: str
    display_name: str
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    organization: str | None
    location_scope: tuple[str, ...]
    authentication_method: str
    identity_provider: str
    identity_mode: str
    development_only: bool
    expires_at: datetime


router = APIRouter(prefix="/api/v1/identity", tags=["identity"])


@router.get("/session", response_model=IdentitySessionResponse)
def get_identity_session(
    request: Request,
    identity: Annotated[VerifiedIdentity, Depends(authenticate_request)],
) -> IdentitySessionResponse:
    """Return only safe display and authorization facts from the verified session."""
    container: AppContainer = request.app.state.container
    provider = container.identity_provider.get_provider_info()
    return IdentitySessionResponse(
        actor_id=identity.actor_id,
        subject_id=identity.subject_id,
        display_name=identity.display_name,
        roles=tuple(sorted(role.value for role in identity.roles)),
        permissions=tuple(sorted(permission.value for permission in identity.permissions)),
        organization=identity.organization,
        location_scope=identity.location_scope,
        authentication_method=identity.authentication_method,
        identity_provider=identity.identity_provider,
        identity_mode=provider.mode,
        development_only=provider.development_only,
        expires_at=identity.expires_at,
    )
