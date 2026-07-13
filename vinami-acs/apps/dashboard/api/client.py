"""Centralized HTTP client for the dashboard; it never accesses persistence directly."""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx


@dataclass(frozen=True, slots=True)
class APIResult:
    status_code: int | None
    payload: dict[str, object] | None
    error: str | None


def base_url() -> str:
    return os.getenv("VINAMI_DASHBOARD_API_BASE_URL", "http://localhost:8000").rstrip("/")


def get(path: str) -> APIResult:
    try:
        response = httpx.get(f"{base_url()}{path}", timeout=3.0)
        payload = response.json()
        return APIResult(response.status_code, payload if isinstance(payload, dict) else None, None)
    except (httpx.HTTPError, ValueError) as error:
        return APIResult(None, None, str(error))
