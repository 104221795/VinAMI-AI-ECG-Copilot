"""Focused authentication and authorization tests for the R1.5 identity boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from vinami.identity.adapters.development import DevelopmentIdentityProvider
from vinami.identity.adapters.oidc import OIDCIdentityProvider
from vinami.identity.application.authorization import ExplicitAuthorizationPolicy
from vinami.identity.domain.security import Permission
from vinami.identity.ports.errors import AuthenticationFailedError, AuthorizationDeniedError
from vinami.identity.ports.provider import AuthenticationRequest


class StaticKeyResolver:
    """Return one deterministic in-process test key without network access."""

    def __init__(self, public_key: object) -> None:
        self._public_key = public_key

    def signing_key(self, token: str) -> object:
        _ = token
        return self._public_key


def _oidc_fixture() -> tuple[OIDCIdentityProvider, object]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    provider = OIDCIdentityProvider(
        issuer="https://issuer.example.invalid",
        audience="vinami-api",
        jwks_url="https://issuer.example.invalid/jwks",
        allowed_algorithms=("RS256",),
        role_claim="roles",
        permission_claim="permissions",
        key_resolver=StaticKeyResolver(private_key.public_key()),
    )
    return provider, private_key


def _claims(**overrides: object) -> dict[str, object]:
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "sub": "clinician-001",
        "name": "Verified Clinician",
        "iss": "https://issuer.example.invalid",
        "aud": "vinami-api",
        "iat": now,
        "nbf": now - timedelta(seconds=1),
        "exp": now + timedelta(minutes=5),
        "jti": "safe-session-reference",
        "roles": ["physician"],
        "permissions": ["identity:inspect"],
        "organization": "hospital-a",
        "locations": ["ED-A"],
    }
    values.update(overrides)
    return values


def _token(private_key: object, **claim_overrides: object) -> str:
    return jwt.encode(
        _claims(**claim_overrides), private_key, algorithm="RS256", headers={"kid": "test-key"}
    )


def test_development_provider_is_deterministic_and_rejects_invented_actor() -> None:
    provider = DevelopmentIdentityProvider()
    request = AuthenticationRequest(development_identity="nurse")

    assert provider.authenticate(request) == provider.authenticate(request)
    assert provider.get_provider_info().development_only is True
    with pytest.raises(AuthenticationFailedError):
        provider.authenticate(AuthenticationRequest(development_identity="invented-administrator"))
    with pytest.raises(AuthenticationFailedError):
        provider.authenticate(AuthenticationRequest(access_token="not-used-in-development"))


def test_explicit_policy_enforces_permissions_for_read_only_and_system_roles() -> None:
    provider = DevelopmentIdentityProvider()
    policy = ExplicitAuthorizationPolicy()
    reviewer = provider.authenticate(
        AuthenticationRequest(development_identity="read_only_reviewer")
    )
    system = provider.authenticate(AuthenticationRequest(development_identity="system_service"))

    assert policy.can(reviewer, Permission.PATIENT_READ)
    assert not policy.can(reviewer, Permission.PATIENT_CREATE)
    with pytest.raises(AuthorizationDeniedError):
        policy.require_permission(reviewer, Permission.PATIENT_CREATE)
    assert policy.can(system, Permission.SYSTEM_READ)
    assert policy.can(system, Permission.CLINICAL_CASE_CREATE)


def test_valid_oidc_token_creates_verified_identity() -> None:
    provider, private_key = _oidc_fixture()
    identity = provider.authenticate(AuthenticationRequest(access_token=_token(private_key)))

    assert identity.subject_id == "clinician-001"
    assert {role.value for role in identity.roles} == {"physician"}
    assert Permission.PATIENT_CREATE in identity.permissions
    assert Permission.IDENTITY_INSPECT in identity.permissions
    assert identity.session_reference == "safe-session-reference"
    assert identity.claims_reference == "kid:test-key"


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://wrong-issuer.example.invalid"},
        {"aud": "wrong-audience"},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"nbf": datetime.now(UTC) + timedelta(minutes=5)},
    ],
)
def test_oidc_rejects_invalid_registered_claims(overrides: dict[str, object]) -> None:
    provider, private_key = _oidc_fixture()
    with pytest.raises(AuthenticationFailedError):
        provider.authenticate(AuthenticationRequest(access_token=_token(private_key, **overrides)))


def test_oidc_rejects_malformed_and_unsupported_algorithm_tokens() -> None:
    provider, _ = _oidc_fixture()
    unsupported = jwt.encode(
        _claims(), "test-secret-that-is-longer-than-32-bytes", algorithm="HS256"
    )

    for token in ("not-a-jwt", unsupported):
        with pytest.raises(AuthenticationFailedError):
            provider.authenticate(AuthenticationRequest(access_token=token))
