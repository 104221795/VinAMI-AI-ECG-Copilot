"""FastAPI application factory exposing only platform-level endpoints in Sprint 2."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST
from sqlalchemy.exc import SQLAlchemyError

from vinami.shared.config import Settings
from vinami.shared.container import AppContainer
from vinami.shared.database import SchemaNotReadyError
from vinami.shared.logging import log_event


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
    async def problem_response(_: Request, error: HTTPException) -> JSONResponse:
        """Return RFC 7807-style errors without exposing implementation details."""
        return JSONResponse(
            status_code=error.status_code,
            content={
                "type": "about:blank",
                "title": "Request failed",
                "status": error.status_code,
                "detail": str(error.detail),
            },
        )

    @app.middleware("http")
    async def record_http_metrics(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))
        request.state.correlation_id = correlation_id
        started_at = perf_counter()
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        elapsed = perf_counter() - started_at
        container.metrics.record_request(
            request.method, request.url.path, response.status_code, elapsed
        )
        return response

    resources = (
        "patients",
        "encounters",
        "clinical-cases",
        "triage",
        "vitals",
        "ecg-studies",
        "ecg-ai-results",
        "troponin",
        "pathways",
        "workflows",
        "tasks",
        "alerts",
        "timeline",
        "audit",
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

        app.get(f"/api/v1/{resource}", tags=[resource], name=f"list_{resource}")(list_resource)

    @app.get("/health", tags=["platform"])
    def health() -> dict[str, str]:
        """Return process liveness without probing external infrastructure."""
        return {"status": "healthy", "service": "vinami-acs-api"}

    @app.get("/ready", tags=["platform"], response_model=None)
    def readiness() -> Response | dict[str, str]:
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
        return {
            "status": "ready",
            "dependency": "postgresql_schema",
            "revision": container.settings.expected_schema_revision,
        }

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        """Expose application-owned Prometheus metrics."""
        return Response(content=container.metrics.render(), media_type=CONTENT_TYPE_LATEST)

    return app
