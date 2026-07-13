"""OIDC bearer-token adapter with JWKS signature and registered-claim verification."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

import jwt
from jwt import InvalidTokenError, PyJWKClient

from vinami.identity.domain.model import ClinicalRole
from vinami.identity.domain.security import ROLE_PERMISSIONS, Permission, VerifiedIdentity
from vinami.identity.ports.errors import AuthenticationFailedError
from vinami.identity.ports.provider import (
    AuthenticationRequest,
    IdentityProviderHealth,
    IdentityProviderInfo,
)


class SigningKeyResolver(Protocol):
    """Resolve a token signing key while allowing deterministic integration tests."""

    def signing_key(self, token: str) -> Any:
        """Return a verification key for one encoded token."""


class PyJWKSigningKeyResolver:
    """Use PyJWT's cached JWKS client with key-rotation support."""

    def __init__(self, jwks_url: str) -> None:
        self._client = PyJWKClient(jwks_url, cache_jwk_set=True, cache_keys=True)

    def signing_key(self, token: str) -> Any:
        """Resolve the current key by token `kid`, refreshing JWKS when needed."""
        return self._client.get_signing_key_from_jwt(token).key


class OIDCIdentityProvider:
    """Verify OIDC JWTs and normalize accepted claims into VinAMI identity contracts."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        allowed_algorithms: tuple[str, ...],
        role_claim: str,
        permission_claim: str,
        key_resolver: SigningKeyResolver | None = None,
    ) -> None:
        if not allowed_algorithms or any(value.lower() == "none" for value in allowed_algorithms):
            raise ValueError("OIDC allowed algorithms must contain signed algorithms")
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._jwks_url = jwks_url
        self._allowed_algorithms = allowed_algorithms
        self._role_claim = role_claim
        self._permission_claim = permission_claim
        self._key_resolver = key_resolver or PyJWKSigningKeyResolver(jwks_url)

    def authenticate(self, request_context: AuthenticationRequest) -> VerifiedIdentity:
        """Verify signature and claims, then map only known roles and permissions."""
        token = request_context.access_token
        if not token:
            raise AuthenticationFailedError("a bearer credential is required")
        try:
            header = jwt.get_unverified_header(token)
            algorithm = str(header.get("alg", ""))
            if algorithm not in self._allowed_algorithms:
                raise AuthenticationFailedError("the bearer credential is not accepted")
            key = self._key_resolver.signing_key(token)
            claims = jwt.decode(
                token,
                key=key,
                algorithms=list(self._allowed_algorithms),
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["sub", "iat", "exp"]},
            )
            return self._identity_from_claims(claims, header)
        except AuthenticationFailedError:
            raise
        except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
            raise AuthenticationFailedError("the bearer credential is not accepted") from error

    def health(self) -> IdentityProviderHealth:
        """Report validated configuration; remote key access is exercised during authentication."""
        return IdentityProviderHealth(True, "oidc", "configured")

    def get_provider_info(self) -> IdentityProviderInfo:
        """Return issuer metadata without exposing audience, keys, or credentials."""
        return IdentityProviderInfo(
            name="external-oidc",
            mode="oidc",
            issuer=self._issuer,
            development_only=False,
        )

    def _identity_from_claims(
        self, claims: Mapping[str, Any], header: Mapping[str, Any]
    ) -> VerifiedIdentity:
        subject = str(claims["sub"])
        roles = _known_values(claims.get(self._role_claim), ClinicalRole)
        if not roles:
            raise AuthenticationFailedError("the verified identity has no recognized role")
        explicit_permissions = _known_values(claims.get(self._permission_claim), Permission)
        permissions = frozenset(explicit_permissions).union(
            *(ROLE_PERMISSIONS[role] for role in roles)
        )
        issued_at = datetime.fromtimestamp(float(claims["iat"]), tz=UTC)
        expires_at = datetime.fromtimestamp(float(claims["exp"]), tz=UTC)
        token_id = _optional_text(claims.get("jti"))
        key_id = _optional_text(header.get("kid"))
        return VerifiedIdentity(
            subject_id=subject,
            actor_id=uuid5(NAMESPACE_URL, f"{self._issuer}|{subject}"),
            display_name=_optional_text(claims.get("name")) or subject,
            email=_optional_text(claims.get("email")),
            directory_reference=_optional_text(claims.get("directory_reference")),
            roles=frozenset(roles),
            permissions=frozenset(permissions),
            organization=_optional_text(claims.get("organization")),
            location_scope=tuple(_strings(claims.get("locations"))),
            authentication_method="oidc_bearer",
            identity_provider=self._issuer,
            issued_at=issued_at,
            expires_at=expires_at,
            session_reference=token_id,
            claims_reference=f"kid:{key_id}" if key_id else None,
        )


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [item for item in value.split() if item]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _known_values[T: (ClinicalRole, Permission)](value: object, enum_type: type[T]) -> set[T]:
    known: set[T] = set()
    for item in _strings(value):
        try:
            known.add(enum_type(item))
        except ValueError:
            continue
    return known


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
