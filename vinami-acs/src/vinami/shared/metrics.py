"""Per-application Prometheus metrics without a module-level mutable registry."""

from __future__ import annotations

from dataclasses import dataclass

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest


@dataclass(slots=True)
class Metrics:
    """Collect delivery-layer request metrics in an application-owned registry."""

    registry: CollectorRegistry
    request_count: Counter
    request_latency: Histogram

    @classmethod
    def create(cls) -> Metrics:
        """Create a registry that belongs to one FastAPI application instance."""
        registry = CollectorRegistry()
        request_count = Counter(
            "vinami_http_requests_total",
            "HTTP requests handled by the VinAMI API.",
            ["method", "path", "status"],
            registry=registry,
        )
        request_latency = Histogram(
            "vinami_http_request_duration_seconds",
            "HTTP request duration in seconds.",
            ["method", "path"],
            registry=registry,
        )
        return cls(registry=registry, request_count=request_count, request_latency=request_latency)

    def record_request(self, method: str, path: str, status: int, duration_seconds: float) -> None:
        """Record one completed HTTP request."""
        self.request_count.labels(method=method, path=path, status=str(status)).inc()
        self.request_latency.labels(method=method, path=path).observe(duration_seconds)

    def render(self) -> bytes:
        """Return Prometheus exposition bytes for the API metrics endpoint."""
        return generate_latest(self.registry)
