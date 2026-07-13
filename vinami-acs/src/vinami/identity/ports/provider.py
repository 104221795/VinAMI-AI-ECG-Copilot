"""Replaceable identity-provider and identity-binding ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from vinami.identity.domain.security import VerifiedIdentity


@dataclass(frozen=True, slots=True)
class AuthenticationRequest:
    """Transport-neutral credentials extracted by a delivery adapter."""

    access_token: str | None = None
    development_identity: str | None = None


@dataclass(frozen=True, slots=True)
class IdentityProviderHealth:
    """Safe readiness state that never includes keys, tokens, or secrets."""

    healthy: bool
    mode: str
    status: str


@dataclass(frozen=True, slots=True)
class IdentityProviderInfo:
    """Non-secret provider metadata suitable for diagnostics."""

    name: str
    mode: str
    issuer: str | None
    development_only: bool


class IdentityProvider(Protocol):
    """Authenticate one request using a replaceable verified identity source."""

    def authenticate(self, request_context: AuthenticationRequest) -> VerifiedIdentity:
        """Return a verified identity or raise a safe authentication error."""

    def health(self) -> IdentityProviderHealth:
        """Return provider readiness without exposing secret configuration."""

    def get_provider_info(self) -> IdentityProviderInfo:
        """Return safe provider metadata."""


class IdentityBinding(Protocol):
    """Bind a verified subject to the stable actor reference used by persistence."""

    def bind(self, identity: VerifiedIdentity) -> None:
        """Idempotently persist or verify the actor-to-subject binding."""
