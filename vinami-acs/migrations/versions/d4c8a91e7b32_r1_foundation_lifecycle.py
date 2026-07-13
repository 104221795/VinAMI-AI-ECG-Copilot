"""R1 foundation clinical lifecycle vertical slice.

Revision ID: d4c8a91e7b32
Revises: a7d3f0b2c6e1
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import vinami.shared.persistence

revision = "d4c8a91e7b32"
down_revision = "a7d3f0b2c6e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add lifecycle versions, persistent idempotency, and explicit projections."""
    op.alter_column("patients", "given_name", existing_type=sa.String(160), nullable=True)
    op.alter_column("patients", "family_name", existing_type=sa.String(160), nullable=True)
    op.add_column("patients", sa.Column("age_band", sa.String(40), nullable=True))
    op.add_column(
        "patients",
        sa.Column(
            "updated_at",
            vinami.shared.persistence.UTCDateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.execute("UPDATE patients SET updated_at=registered_at")
    op.alter_column("patients", "updated_at", server_default=None)
    op.add_column(
        "patients", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.alter_column("patients", "version", server_default=None)
    op.create_index("ix_patients_updated_at", "patients", ["updated_at"])

    op.add_column(
        "encounters",
        sa.Column(
            "created_at",
            vinami.shared.persistence.UTCDateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column(
        "encounters",
        sa.Column(
            "updated_at",
            vinami.shared.persistence.UTCDateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.execute("UPDATE encounters SET created_at=started_at, updated_at=started_at")
    op.alter_column("encounters", "created_at", server_default=None)
    op.alter_column("encounters", "updated_at", server_default=None)
    op.add_column(
        "encounters", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.alter_column("encounters", "version", server_default=None)
    op.create_index("ix_encounters_updated_at", "encounters", ["updated_at"])

    op.add_column(
        "clinical_cases",
        sa.Column(
            "updated_at",
            vinami.shared.persistence.UTCDateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.execute("UPDATE clinical_cases SET updated_at=COALESCE(closed_at, opened_at)")
    op.alter_column("clinical_cases", "updated_at", server_default=None)
    op.create_index("ix_clinical_cases_updated_at", "clinical_cases", ["updated_at"])
    op.create_index(
        "uq_clinical_cases_active_encounter",
        "clinical_cases",
        ["encounter_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('OPEN', 'UNDER_REVIEW')"),
    )

    op.create_table(
        "command_idempotency",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("command_type", sa.String(120), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(120), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column(
            "response_payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "created_at", vinami.shared.persistence.UTCDateTime(timezone=True), nullable=False
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["clinical_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("command_id"),
        sa.UniqueConstraint(
            "actor_id", "command_type", "idempotency_key", name="uq_command_idempotency_scope"
        ),
    )
    op.create_index("ix_command_idempotency_actor_id", "command_idempotency", ["actor_id"])
    op.create_index("ix_command_idempotency_created_at", "command_idempotency", ["created_at"])
    op.create_index("ix_command_idempotency_resource_id", "command_idempotency", ["resource_id"])

    op.add_column(
        "audit_logs",
        sa.Column("request_source", sa.String(160), nullable=False, server_default="legacy"),
    )
    op.alter_column("audit_logs", "request_source", server_default=None)

    op.drop_constraint("uq_timeline_events_source_event_id", "timeline_events", type_="unique")
    op.add_column(
        "timeline_events",
        sa.Column("title", sa.String(240), nullable=False, server_default="Legacy lifecycle event"),
    )
    op.add_column(
        "timeline_events",
        sa.Column(
            "recorded_at",
            vinami.shared.persistence.UTCDateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column(
        "timeline_events",
        sa.Column("source", sa.String(160), nullable=False, server_default="legacy_projection"),
    )
    op.add_column("timeline_events", sa.Column("actor_id", sa.Uuid(), nullable=True))
    op.add_column(
        "timeline_events",
        sa.Column(
            "correlation_id",
            sa.Uuid(),
            nullable=False,
            server_default="00000000-0000-0000-0000-000000000000",
        ),
    )
    op.add_column("timeline_events", sa.Column("causation_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_timeline_events_actor", "timeline_events", "clinical_users", ["actor_id"], ["id"],
        ondelete="SET NULL"
    )
    op.create_unique_constraint(
        "uq_timeline_case_source_event", "timeline_events", ["case_id", "source_event_id"]
    )
    op.create_index("ix_timeline_events_recorded_at", "timeline_events", ["recorded_at"])
    op.create_index("ix_timeline_events_correlation_id", "timeline_events", ["correlation_id"])
    op.create_index("ix_timeline_events_causation_id", "timeline_events", ["causation_id"])
    for column in ("title", "recorded_at", "source", "correlation_id"):
        op.alter_column("timeline_events", column, server_default=None)


def downgrade() -> None:
    """Remove R1 additions; lifecycle projections may be regenerated from the outbox."""
    op.drop_index("ix_timeline_events_causation_id", table_name="timeline_events")
    op.drop_index("ix_timeline_events_correlation_id", table_name="timeline_events")
    op.drop_index("ix_timeline_events_recorded_at", table_name="timeline_events")
    op.drop_constraint("uq_timeline_case_source_event", "timeline_events", type_="unique")
    op.drop_constraint("fk_timeline_events_actor", "timeline_events", type_="foreignkey")
    op.execute(
        "DELETE FROM timeline_events a USING timeline_events b "
        "WHERE a.source_event_id=b.source_event_id AND a.source_event_id IS NOT NULL AND a.id>b.id"
    )
    op.create_unique_constraint(
        "uq_timeline_events_source_event_id", "timeline_events", ["source_event_id"]
    )
    for column in (
        "causation_id",
        "correlation_id",
        "actor_id",
        "source",
        "recorded_at",
        "title",
    ):
        op.drop_column("timeline_events", column)
    op.drop_column("audit_logs", "request_source")
    op.drop_index("ix_command_idempotency_resource_id", table_name="command_idempotency")
    op.drop_index("ix_command_idempotency_created_at", table_name="command_idempotency")
    op.drop_index("ix_command_idempotency_actor_id", table_name="command_idempotency")
    op.drop_table("command_idempotency")
    op.drop_index("uq_clinical_cases_active_encounter", table_name="clinical_cases")
    op.drop_index("ix_clinical_cases_updated_at", table_name="clinical_cases")
    op.drop_column("clinical_cases", "updated_at")
    op.drop_index("ix_encounters_updated_at", table_name="encounters")
    for column in ("version", "updated_at", "created_at"):
        op.drop_column("encounters", column)
    op.drop_index("ix_patients_updated_at", table_name="patients")
    for column in ("version", "updated_at", "age_band"):
        op.drop_column("patients", column)
    op.execute(
        "UPDATE patients SET given_name=COALESCE(given_name, 'Legacy'), "
        "family_name=COALESCE(family_name, 'Patient')"
    )
    op.alter_column("patients", "family_name", existing_type=sa.String(160), nullable=False)
    op.alter_column("patients", "given_name", existing_type=sa.String(160), nullable=False)
