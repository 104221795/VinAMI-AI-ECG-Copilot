"""Persistence-backed structural actor authorization for recovery commands."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from vinami.identity.adapters.persistence import ClinicalUserRecord


class SQLAlchemyActorAuthorizationRepository:
    """Resolve an actor role from the system-of-record identity placeholder."""

    def __init__(self, session: Session) -> None:
        """Bind actor lookups to the active command transaction."""
        self._session = session

    def role_for(self, actor_id: UUID) -> str | None:
        """Return the stored role value for a known actor."""
        record = self._session.get(ClinicalUserRecord, actor_id)
        return record.role.value if record is not None else None
