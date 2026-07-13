"""Deterministic development identity provider and seed actor bootstrap."""

from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.orm import Session, sessionmaker

from vinami.identity.adapters.persistence import ClinicalUserRecord
from vinami.identity.domain.model import ClinicalRole, ClinicalUser
from vinami.identity.domain.security import ROLE_PERMISSIONS, VerifiedIdentity
from vinami.identity.ports.errors import AuthenticationFailedError
from vinami.identity.ports.provider import (
    AuthenticationRequest,
    IdentityProviderHealth,
    IdentityProviderInfo,
)

_ISSUED_AT = datetime(2026, 1, 1, tzinfo=UTC)
_EXPIRES_AT = datetime(2099, 1, 1, tzinfo=UTC)


def _fixture(key: str, display_name: str, role: ClinicalRole) -> VerifiedIdentity:
    subject = f"development:{key}"
    return VerifiedIdentity(
        subject_id=subject,
        actor_id=uuid5(NAMESPACE_URL, f"vinami:{subject}"),
        display_name=display_name,
        email=f"{key}@example.invalid",
        directory_reference=None,
        roles=frozenset({role}),
        permissions=ROLE_PERMISSIONS[role],
        organization="vinami-synthetic",
        location_scope=("Emergency Department",),
        authentication_method="development_fixture",
        identity_provider="vinami-development",
        issued_at=_ISSUED_AT,
        expires_at=_EXPIRES_AT,
        session_reference=f"development-session:{key}",
        claims_reference=f"fixture:{key}",
    )


DEVELOPMENT_IDENTITIES = MappingProxyType(
    {
        "physician": _fixture("physician", "Synthetic Physician", ClinicalRole.PHYSICIAN),
        "nurse": _fixture("nurse", "Synthetic Nurse", ClinicalRole.NURSE),
        "technician": _fixture("technician", "Synthetic Technician", ClinicalRole.TECHNICIAN),
        "care_coordinator": _fixture(
            "care_coordinator", "Synthetic Care Coordinator", ClinicalRole.CARE_COORDINATOR
        ),
        "administrator": _fixture(
            "administrator", "Synthetic Administrator", ClinicalRole.ADMINISTRATOR
        ),
        "auditor": _fixture("auditor", "Synthetic Auditor", ClinicalRole.AUDITOR),
        "system_service": _fixture(
            "system_service", "Synthetic System Service", ClinicalRole.SYSTEM_SERVICE
        ),
        "read_only_reviewer": _fixture(
            "read_only_reviewer",
            "Synthetic Read-only Reviewer",
            ClinicalRole.READ_ONLY_REVIEWER,
        ),
    }
)


class DevelopmentIdentityProvider:
    """Authenticate only predefined synthetic identities selected by fixture key."""

    def authenticate(self, request_context: AuthenticationRequest) -> VerifiedIdentity:
        """Resolve a deterministic fixture and reject invented actors or bearer tokens."""
        if request_context.access_token is not None:
            raise AuthenticationFailedError(
                "bearer credentials are not accepted in development mode"
            )
        selector = (request_context.development_identity or "").strip().lower()
        identity = DEVELOPMENT_IDENTITIES.get(selector)
        if identity is None:
            raise AuthenticationFailedError("a configured development identity is required")
        return identity

    def health(self) -> IdentityProviderHealth:
        """Expose an unmistakable development-only readiness state."""
        return IdentityProviderHealth(True, "development", "development_identity_mode")

    def get_provider_info(self) -> IdentityProviderInfo:
        """Return non-secret development provider metadata."""
        return IdentityProviderInfo(
            name="vinami-development",
            mode="development",
            issuer=None,
            development_only=True,
        )


class DevelopmentIdentityAdapter:
    """Persist an actor reference without credentials or an authentication claim."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def ensure_actor(self, actor: ClinicalUser) -> None:
        """Create an actor once and reject conflicting persisted identity data."""
        with self._session_factory() as session:
            existing = session.get(ClinicalUserRecord, actor.id)
            if existing is None:
                session.add(
                    ClinicalUserRecord(
                        id=actor.id,
                        display_name=actor.display_name,
                        role=actor.role,
                        team_id=actor.team_id,
                    )
                )
                session.commit()
                return
            if existing.role is not actor.role or existing.display_name != actor.display_name:
                raise RuntimeError("development actor identifier conflicts with persisted identity")
