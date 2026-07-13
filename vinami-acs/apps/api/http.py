"""Shared HTTP-only contracts and command-header parsing for the R1 API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Header, Request
from pydantic import BaseModel, ConfigDict

from vinami.shared.actor import ActorContext
from vinami.shared.application_errors import ActorContextError
from vinami.shared.domain import require_text


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
class CommandHeaders:
    """Validated R1 command metadata supplied by the development delivery adapter."""

    actor: ActorContext
    idempotency_key: str


def command_headers(
    request: Request,
    actor_id: Annotated[
        str | None,
        Header(alias="X-Actor-ID", description="Development actor UUID; not authenticated"),
    ] = None,
    actor_role: Annotated[
        str | None,
        Header(alias="X-Actor-Role", description="Structurally validated development role"),
    ] = None,
    correlation_id: Annotated[
        str | None,
        Header(alias="X-Correlation-ID", description="Caller-provided request correlation UUID"),
    ] = None,
    request_source: Annotated[
        str | None,
        Header(alias="X-Request-Source", description="Calling application or adapter name"),
    ] = None,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", description="Persistent command deduplication key"),
    ] = None,
) -> CommandHeaders:
    """Require and structurally validate all command provenance headers."""
    missing = [
        name
        for name, value in (
            ("X-Actor-ID", actor_id),
            ("X-Actor-Role", actor_role),
            ("X-Correlation-ID", correlation_id),
            ("X-Request-Source", request_source),
            ("Idempotency-Key", idempotency_key),
        )
        if value is None
    ]
    if missing:
        raise ActorContextError(f"missing required command headers: {', '.join(missing)}")
    assert actor_id is not None
    assert actor_role is not None
    assert correlation_id is not None
    assert request_source is not None
    assert idempotency_key is not None
    try:
        parsed_actor_id = UUID(actor_id)
        parsed_correlation_id = UUID(correlation_id)
    except ValueError as error:
        raise ActorContextError("actor and correlation headers must contain valid UUIDs") from error
    actor = ActorContext(
        actor_id=parsed_actor_id,
        actor_role=require_text(actor_role.lower(), "actor_role"),
        correlation_id=parsed_correlation_id,
        request_source=require_text(request_source, "request_source"),
    )
    return CommandHeaders(actor, require_text(idempotency_key, "idempotency_key"))
