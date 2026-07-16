"""FastAPI application factory exposing only platform-level endpoints in Sprint 2."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from apps.api.case_workspace import router as case_workspace_router
from apps.api.clinical_reasoning import router as clinical_reasoning_router
from apps.api.command_center import router as command_center_router
from apps.api.ecg import router as ecg_router
from apps.api.http import audit_request_outcome, authorize_for
from apps.api.history import router as history_router
from apps.api.identity import router as identity_router
from apps.api.lifecycle import router as lifecycle_router
from apps.api.triage_vitals import router as triage_vitals_router
from apps.api.troponin import router as troponin_router
from apps.api.workflow_operations import router as workflow_operations_router
from vinami.identity.domain.security import Permission
from vinami.identity.ports.errors import AuthenticationFailedError, AuthorizationDeniedError
from vinami.shared.application_errors import (
    ActorContextError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from vinami.shared.config import Settings
from vinami.shared.container import AppContainer
from vinami.shared.database import SchemaNotReadyError
from vinami.shared.domain import DomainInvariantError, OptimisticConcurrencyError
from vinami.shared.logging import log_event
from vinami.troponin.domain.evidence import TroponinUnitValidationError


def create_app(settings: Settings | None = None) -> FastAPI:
    """Compose the HTTP application without importing clinical bounded-context behavior."""
    container = AppContainer.create(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        log_event(container.logger, "api_started", environment=container.settings.app_environment)
        try:
            yield
        finally:
            container.database.dispose()
            log_event(container.logger, "api_stopped")

    app = FastAPI(
        title=container.settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.container = container

    @app.exception_handler(HTTPException)
    async def problem_response(request: Request, error: HTTPException) -> JSONResponse:
        """Return RFC 7807-style errors without exposing implementation details."""
        return _problem(
            request,
            error.status_code,
            "Request failed",
            str(error.detail),
            "https://vinami.example/problems/http-request",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_problem(request: Request, error: RequestValidationError) -> JSONResponse:
        errors = []
        for item in error.errors():
            location = item.get("loc", ())
            field = str(location[-1]) if location else "request"
            if field == "unit":
                code = "unit_required" if item.get("type") == "missing" else "incompatible_unit"
                errors.append({"field": "unit", "code": code})
        return _problem(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Request validation failed",
            "The request does not satisfy the documented API contract.",
            "https://vinami.example/problems/validation",
            errors=errors or None,
        )

    @app.exception_handler(ActorContextError)
    async def actor_problem(request: Request, error: ActorContextError) -> JSONResponse:
        return _problem(
            request,
            status.HTTP_400_BAD_REQUEST,
            "Invalid command context",
            str(error),
            "https://vinami.example/problems/actor-context",
        )

    @app.exception_handler(AuthenticationFailedError)
    async def authentication_problem(
        request: Request, _: AuthenticationFailedError
    ) -> JSONResponse:
        return _problem(
            request,
            status.HTTP_401_UNAUTHORIZED,
            "Authentication required",
            "A valid identity from the configured provider is required.",
            "https://vinami.example/problems/authentication",
            extra_headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(AuthorizationDeniedError)
    async def authorization_problem(request: Request, _: AuthorizationDeniedError) -> JSONResponse:
        return _problem(
            request,
            status.HTTP_403_FORBIDDEN,
            "Permission denied",
            "The verified identity cannot perform this operation.",
            "https://vinami.example/problems/authorization",
        )

    @app.exception_handler(ResourceNotFoundError)
    async def not_found_problem(request: Request, error: ResourceNotFoundError) -> JSONResponse:
        return _problem(
            request,
            status.HTTP_404_NOT_FOUND,
            "Resource not found",
            str(error),
            "https://vinami.example/problems/not-found",
        )

    @app.exception_handler(ResourceConflictError)
    async def conflict_problem(request: Request, error: ResourceConflictError) -> JSONResponse:
        audit_request_outcome(request, "domain_rejection", "request:domain_rejected")
        return _problem(
            request,
            status.HTTP_409_CONFLICT,
            "Resource conflict",
            str(error),
            "https://vinami.example/problems/conflict",
        )

    @app.exception_handler(OptimisticConcurrencyError)
    async def concurrency_problem(
        request: Request, error: OptimisticConcurrencyError
    ) -> JSONResponse:
        audit_request_outcome(request, "concurrency_conflict", "request:concurrency_conflict")
        return _problem(
            request,
            status.HTTP_409_CONFLICT,
            "Concurrency conflict",
            str(error),
            "https://vinami.example/problems/concurrency",
        )

    @app.exception_handler(DomainInvariantError)
    async def invariant_problem(request: Request, error: DomainInvariantError) -> JSONResponse:
        audit_request_outcome(request, "domain_rejection", "request:domain_rejected")
        return _problem(
            request,
            status.HTTP_400_BAD_REQUEST,
            "Invalid lifecycle command",
            str(error),
            "https://vinami.example/problems/domain-invariant",
        )

    @app.exception_handler(TroponinUnitValidationError)
    async def troponin_unit_problem(
        request: Request, error: TroponinUnitValidationError
    ) -> JSONResponse:
        audit_request_outcome(request, "domain_rejection", "request:troponin_unit_rejected")
        return _problem(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Invalid troponin unit",
            str(error),
            f"https://vinami.example/problems/{error.code}",
            errors=[{"field": error.field, "code": error.code}],
        )

    @app.exception_handler(IntegrityError)
    async def integrity_problem(request: Request, _: IntegrityError) -> JSONResponse:
        audit_request_outcome(request, "concurrency_conflict", "request:persistence_conflict")
        return _problem(
            request,
            status.HTTP_409_CONFLICT,
            "Persistence conflict",
            "The request conflicts with an existing persisted resource.",
            "https://vinami.example/problems/persistence-conflict",
        )

    @app.exception_handler(SQLAlchemyError)
    async def persistence_problem(request: Request, _: SQLAlchemyError) -> JSONResponse:
        return _problem(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Persistence failure",
            "The operation could not be completed.",
            "https://vinami.example/problems/persistence",
        )

    @app.middleware("http")
    async def record_http_metrics(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        supplied_correlation = request.headers.get("X-Correlation-ID")
        try:
            correlation_id = (
                str(UUID(supplied_correlation)) if supplied_correlation else str(uuid4())
            )
        except ValueError:
            correlation_id = str(uuid4())
            request.state.correlation_id = correlation_id
            return _problem(
                request,
                status.HTTP_400_BAD_REQUEST,
                "Invalid correlation identifier",
                "X-Correlation-ID must contain a UUID.",
                "https://vinami.example/problems/correlation-id",
            )
        request.state.correlation_id = correlation_id
        started_at = perf_counter()
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        elapsed = perf_counter() - started_at
        container.metrics.record_request(
            request.method, request.url.path, response.status_code, elapsed
        )
        return response

    app.include_router(lifecycle_router)
    app.include_router(triage_vitals_router)
    app.include_router(identity_router)
    app.include_router(ecg_router)
    app.include_router(troponin_router)
    app.include_router(clinical_reasoning_router)
    app.include_router(workflow_operations_router)
    app.include_router(command_center_router)
    app.include_router(case_workspace_router)
    app.include_router(history_router)

    resources = (
        "triage",
        "vitals",
        "pathways",
        "workflows",
        "tasks",
        "alerts",
        "model-registry",
    )
    for resource in resources:

        def list_resource(
            page: int = Query(1, ge=1),
            page_size: int = Query(25, ge=1, le=100),
            resource_name: str = resource,
        ) -> dict[str, object]:
            """Provide a stable paginated surface pending context-specific query handlers."""
            return {
                "resource": resource_name,
                "items": [],
                "page": page,
                "page_size": page_size,
                "total": 0,
            }

        app.get(
            f"/api/v1/{resource}",
            tags=[resource],
            name=f"list_{resource}",
            dependencies=[Depends(authorize_for(Permission.SYSTEM_READ))],
        )(list_resource)

    @app.get("/health", tags=["platform"])
    def health() -> dict[str, str]:
        """Return process liveness without probing external infrastructure."""
        return {"status": "healthy", "service": "vinami-acs-api"}

    @app.get("/ready", tags=["platform"], response_model=None)
    def readiness() -> Response | dict[str, object]:
        """Return readiness only when the configured database accepts a probe."""
        try:
            container.database.probe_readiness()
        except (SQLAlchemyError, SchemaNotReadyError) as error:
            log_event(container.logger, "readiness_failed", dependency="postgresql")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "not_ready",
                    "dependency": "postgresql_schema",
                    "reason": type(error).__name__,
                },
            )
        identity_health = container.identity_provider.health()
        provider_info = container.identity_provider.get_provider_info()
        if not identity_health.healthy:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "not_ready",
                    "dependency": "identity_provider",
                    "identity_mode": identity_health.mode,
                },
            )
        return {
            "status": "ready",
            "dependency": "postgresql_schema",
            "revision": container.settings.expected_schema_revision,
            "identity": {
                "mode": identity_health.mode,
                "status": identity_health.status,
                "provider": provider_info.name,
                "development_only": provider_info.development_only,
            },
        }

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        """Expose application-owned Prometheus metrics."""
        return Response(content=container.metrics.render(), media_type=CONTENT_TYPE_LATEST)

    return app


def _problem(
    request: Request,
    status_code: int,
    title: str,
    detail: str,
    problem_type: str,
    extra_headers: dict[str, str] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    """Build one safe RFC 7807 document and preserve the request correlation identifier."""
    correlation = getattr(request.state, "correlation_id", None) or str(uuid4())
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        content={
            "type": problem_type,
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": request.url.path,
            "correlation_id": correlation,
            **({"errors": errors} if errors else {}),
        },
        headers={"X-Correlation-ID": correlation, **(extra_headers or {})},
    )
