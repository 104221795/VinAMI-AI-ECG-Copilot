"""Safe identity-boundary errors independent of HTTP or provider SDKs."""


class AuthenticationFailedError(RuntimeError):
    """Raised when a credential cannot be verified by the configured provider."""


class AuthorizationDeniedError(RuntimeError):
    """Raised when a verified identity lacks an application permission."""
