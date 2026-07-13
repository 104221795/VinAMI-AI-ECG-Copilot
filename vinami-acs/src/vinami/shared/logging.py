"""Structured logging configuration isolated from domain code."""

from __future__ import annotations

import logging
from typing import Any, cast

import structlog

from vinami.shared.config import Settings


def configure_logging(settings: Settings) -> structlog.stdlib.BoundLogger:
    """Configure JSON structured logging once at the delivery composition root."""
    level = logging.getLevelName(settings.log_level.upper())
    if not isinstance(level, int):
        raise ValueError(f"Unsupported log level: {settings.log_level}")
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger("vinami"))


def log_event(logger: structlog.stdlib.BoundLogger, event: str, **fields: Any) -> None:
    """Emit a structured technical event without accepting clinical payloads."""
    logger.info(event, **fields)
