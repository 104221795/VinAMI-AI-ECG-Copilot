"""internal_event_delivery

Revision ID: c4d7e8f9a1b2
Revises: e8925090e0cb
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import vinami.shared.persistence

revision = "c4d7e8f9a1b2"
down_revision = "e8925090e0cb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add durable envelope, retry, idempotency, and projection-source fields."""
    op.add_column(
        "outbox_events",
        sa.Column("event_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("outbox_events", sa.Column("correlation_id", sa.Uuid(), nullable=True))
    op.add_column("outbox_events", sa.Column("causation_id", sa.Uuid(), nullable=True))
    op.add_column("outbox_events", sa.Column("actor_id", sa.Uuid(), nullable=True))
    op.add_column(
        "outbox_events",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "outbox_events",
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
    )
    op.add_column(
        "outbox_events", sa.Column("available_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "outbox_events", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "outbox_events", sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute("UPDATE outbox_events SET correlation_id = event_id WHERE correlation_id IS NULL")
    op.execute("UPDATE outbox_events SET available_at = occurred_at WHERE available_at IS NULL")
    op.alter_column("outbox_events", "correlation_id", nullable=False)
    op.alter_column("outbox_events", "available_at", nullable=False)
    op.create_index("ix_outbox_events_correlation_id", "outbox_events", ["correlation_id"])
    op.create_index("ix_outbox_events_causation_id", "outbox_events", ["causation_id"])
    op.create_index("ix_outbox_events_actor_id", "outbox_events", ["actor_id"])
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_available_at", "outbox_events", ["available_at"])
    op.create_index("ix_outbox_events_claimed_at", "outbox_events", ["claimed_at"])

    op.create_table(
        "event_consumptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("handler_name", sa.String(length=240), nullable=False),
        sa.Column(
            "consumed_at",
            vinami.shared.persistence.UTCDateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["event_id"], ["outbox_events.event_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "handler_name", name="uq_event_consumption_handler"),
    )
    op.create_index("ix_event_consumptions_event_id", "event_consumptions", ["event_id"])
    op.create_index("ix_event_consumptions_consumed_at", "event_consumptions", ["consumed_at"])

    op.add_column("audit_logs", sa.Column("source_event_id", sa.Uuid(), nullable=True))
    op.add_column("timeline_events", sa.Column("source_event_id", sa.Uuid(), nullable=True))
    op.create_unique_constraint("uq_audit_logs_source_event_id", "audit_logs", ["source_event_id"])
    op.create_unique_constraint(
        "uq_timeline_events_source_event_id",
        "timeline_events",
        ["source_event_id"],
    )


def downgrade() -> None:
    """Remove internal event delivery state and return to the Sprint 3 outbox schema."""
    op.drop_constraint("uq_timeline_events_source_event_id", "timeline_events", type_="unique")
    op.drop_constraint("uq_audit_logs_source_event_id", "audit_logs", type_="unique")
    op.drop_column("timeline_events", "source_event_id")
    op.drop_column("audit_logs", "source_event_id")
    op.drop_index("ix_event_consumptions_consumed_at", table_name="event_consumptions")
    op.drop_index("ix_event_consumptions_event_id", table_name="event_consumptions")
    op.drop_table("event_consumptions")
    op.drop_index("ix_outbox_events_claimed_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_available_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status", table_name="outbox_events")
    op.drop_index("ix_outbox_events_actor_id", table_name="outbox_events")
    op.drop_index("ix_outbox_events_causation_id", table_name="outbox_events")
    op.drop_index("ix_outbox_events_correlation_id", table_name="outbox_events")
    op.drop_column("outbox_events", "last_attempt_at")
    op.drop_column("outbox_events", "claimed_at")
    op.drop_column("outbox_events", "available_at")
    op.drop_column("outbox_events", "status")
    op.drop_column("outbox_events", "metadata")
    op.drop_column("outbox_events", "actor_id")
    op.drop_column("outbox_events", "causation_id")
    op.drop_column("outbox_events", "correlation_id")
    op.drop_column("outbox_events", "event_version")
