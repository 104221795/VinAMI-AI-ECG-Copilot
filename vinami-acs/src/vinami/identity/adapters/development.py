"""Development-only identity bootstrap used by deterministic synthetic seed data."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from vinami.identity.adapters.persistence import ClinicalUserRecord
from vinami.identity.domain.model import ClinicalUser


class DevelopmentIdentityAdapter:
    """Persist an actor reference without credentials or an authentication claim."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def ensure_actor(self, actor: ClinicalUser) -> None:
        """Create an actor once and reject conflicting persisted identity data."""
        with self._session_factory() as session:
            existing = session.get(ClinicalUserRecord, actor.id)
            if existing is None:
                session.add(
                    ClinicalUserRecord(
                        id=actor.id,
                        display_name=actor.display_name,
                        role=actor.role,
                        team_id=actor.team_id,
                    )
                )
                session.commit()
                return
            if existing.role is not actor.role or existing.display_name != actor.display_name:
                raise RuntimeError("development actor identifier conflicts with persisted identity")
