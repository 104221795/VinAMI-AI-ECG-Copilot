"""Transport-independent failures raised by application use cases."""

from __future__ import annotations


class ApplicationError(RuntimeError):
    """Base class for expected application failures safe to map at delivery boundaries."""


class ResourceNotFoundError(ApplicationError):
    """A requested aggregate or required parent resource does not exist."""


class ResourceConflictError(ApplicationError):
    """A uniqueness or lifecycle policy conflicts with the requested operation."""


class IdempotencyConflictError(ResourceConflictError):
    """An idempotency key was reused with a different command payload."""


class ActorContextError(ApplicationError):
    """The structurally supplied development actor does not match persisted identity data."""
