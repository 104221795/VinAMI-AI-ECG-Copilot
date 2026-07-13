"""SQLAlchemy persistence primitives kept outside every domain layer."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    """Declarative base used only by infrastructure adapter mappings."""


class UTCDateTime(TypeDecorator[datetime]):
    """Persist only timezone-aware UTC timestamps, including on non-PostgreSQL test engines."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        """Normalize outgoing timestamps to UTC."""
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("UTCDateTime requires timezone-aware values")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        """Normalize incoming database timestamps to UTC."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


JSONDocument = JSON().with_variant(JSONB, "postgresql")
UUIDType = Uuid(as_uuid=True)
