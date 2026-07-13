"""PostgreSQL binding between verified provider subjects and stable actor references."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from vinami.identity.adapters.persistence import ClinicalUserRecord
from vinami.identity.domain.security import VerifiedIdentity
from vinami.identity.ports.errors import AuthenticationFailedError


class SQLAlchemyIdentityBinding:
    """Idempotently persist a verified subject without storing credentials or raw claims."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def bind(self, identity: VerifiedIdentity) -> None:
        """Create or verify one immutable provider-subject to actor association."""
        with self._session_factory() as session:
            existing = session.scalar(
                select(ClinicalUserRecord)
                .where(ClinicalUserRecord.id == identity.actor_id)
                .with_for_update()
            )
            if existing is None:
                session.add(
                    ClinicalUserRecord(
                        id=identity.actor_id,
                        display_name=identity.display_name,
                        role=identity.primary_role,
                        team_id=None,
                        identity_subject=identity.subject_id,
                        identity_provider=identity.identity_provider,
                        authentication_method=identity.authentication_method,
                        organization=identity.organization,
                        location_scope=list(identity.location_scope),
                    )
                )
                session.commit()
                return
            if (
                existing.identity_subject != identity.subject_id
                or existing.identity_provider != identity.identity_provider
            ):
                raise AuthenticationFailedError("verified identity binding conflicts with actor")
            existing.display_name = identity.display_name
            existing.role = identity.primary_role
            existing.authentication_method = identity.authentication_method
            existing.organization = identity.organization
            existing.location_scope = list(identity.location_scope)
            session.commit()
