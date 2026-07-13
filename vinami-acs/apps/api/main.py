"""Uvicorn import target for the API application factory."""

from apps.api.app import create_app

__all__ = ["create_app"]
