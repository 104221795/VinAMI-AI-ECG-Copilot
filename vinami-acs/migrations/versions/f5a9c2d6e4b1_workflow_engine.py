"""workflow_engine

Revision ID: f5a9c2d6e4b1
Revises: c4d7e8f9a1b2
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import vinami.shared.persistence

revision = "f5a9c2d6e4b1"
down_revision = "c4d7e8f9a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Persist explicit, non-clinical workflow state-machine provenance and effects."""
    workflow_state_values = (
        "NEW",
        "TRIAGE_IN_PROGRESS",
        "AWAITING_ECG",
        "ECG_UNDER_REVIEW",
        "AWAITING_TROPONIN",
        "OBSERVATION",
        "PHYSICIAN_REVIEW_REQUIRED",
        "PATHWAY_SELECTED",
        "TRANSFER_IN_PROGRESS",
        "CATH_LAB_REVIEW",
        "DISCHARGE_REVIEW",
        "CLOSED",
        "CANCELLED",
    )
    workflow_state = postgresql.ENUM(*workflow_state_values, name="workflow_state")
    workflow_state_column = postgresql.ENUM(
        *workflow_state_values, name="workflow_state", create_type=False
    )
    timer_status = postgresql.ENUM(
        "SCHEDULED", "COMPLETED", "CANCELLED", name="workflow_due_timer_status"
    )
    timer_status_column = postgresql.ENUM(
        "SCHEDULED", "COMPLETED", "CANCELLED", name="workflow_due_timer_status", create_type=False
    )
    workflow_state.create(op.get_bind(), checkfirst=True)
    timer_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "clinical_workflows",
        sa.Column(
            "definition_id", sa.String(160), nullable=False, server_default="legacy-workflow"
        ),
    )
    op.add_column(
        "clinical_workflows",
        sa.Column("definition_version", sa.String(80), nullable=False, server_default="0"),
    )
    op.add_column(
        "clinical_workflows",
        sa.Column(
            "demonstration_notice",
            sa.String(200),
            nullable=False,
            server_default="Demonstration workflow — not for clinical use.",
        ),
    )
    op.add_column(
        "clinical_workflows",
        sa.Column("current_state", workflow_state_column, nullable=False, server_default="NEW"),
    )
    op.add_column(
        "clinical_workflows",
        sa.Column(
            "facts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "clinical_workflows",
        sa.Column(
            "last_transition_at",
            vinami.shared.persistence.UTCDateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index("ix_clinical_workflows_current_state", "clinical_workflows", ["current_state"])

    op.add_column("clinical_tasks", sa.Column("workflow_command_id", sa.Uuid(), nullable=True))
    op.add_column("clinical_tasks", sa.Column("workflow_effect", sa.String(160), nullable=True))
    op.create_unique_constraint(
        "uq_clinical_task_workflow_effect",
        "clinical_tasks",
        ["workflow_id", "workflow_command_id", "workflow_effect"],
    )
    op.add_column("alerts", sa.Column("workflow_id", sa.Uuid(), nullable=True))
    op.add_column("alerts", sa.Column("workflow_command_id", sa.Uuid(), nullable=True))
    op.add_column("alerts", sa.Column("workflow_effect", sa.String(160), nullable=True))
    op.create_foreign_key(
        "fk_alerts_workflow_id",
        "alerts",
        "clinical_workflows",
        ["workflow_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_alerts_workflow_id", "alerts", ["workflow_id"])
    op.create_unique_constraint(
        "uq_alert_workflow_effect",
        "alerts",
        ["workflow_id", "workflow_command_id", "workflow_effect"],
    )

    op.create_table(
        "workflow_transition_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("transition_name", sa.String(160), nullable=False),
        sa.Column("from_state", workflow_state_column, nullable=False),
        sa.Column("to_state", workflow_state_column, nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "occurred_at", vinami.shared.persistence.UTCDateTime(timezone=True), nullable=False
        ),
        sa.Column("facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["clinical_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_id"], ["clinical_workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "command_id", name="uq_workflow_transition_command"),
    )
    op.create_index(
        "ix_workflow_transition_history_workflow_id", "workflow_transition_history", ["workflow_id"]
    )
    op.create_index(
        "ix_workflow_transition_history_command_id", "workflow_transition_history", ["command_id"]
    )
    op.create_index(
        "ix_workflow_transition_history_occurred_at", "workflow_transition_history", ["occurred_at"]
    )
    op.create_table(
        "workflow_due_timers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(160), nullable=False),
        sa.Column("due_at", vinami.shared.persistence.UTCDateTime(timezone=True), nullable=False),
        sa.Column("command_type", sa.String(120), nullable=False),
        sa.Column("facts_patch", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", timer_status_column, nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["clinical_workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "key", name="uq_workflow_timer_key"),
    )
    op.create_index("ix_workflow_due_timers_workflow_id", "workflow_due_timers", ["workflow_id"])
    op.create_index("ix_workflow_due_timers_due_at", "workflow_due_timers", ["due_at"])
    op.create_index("ix_workflow_due_timers_status", "workflow_due_timers", ["status"])
    op.create_table(
        "workflow_command_receipts",
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("resulting_state", workflow_state_column, nullable=False),
        sa.Column(
            "processed_at", vinami.shared.persistence.UTCDateTime(timezone=True), nullable=False
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["clinical_workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("command_id"),
    )
    op.create_index(
        "ix_workflow_command_receipts_workflow_id", "workflow_command_receipts", ["workflow_id"]
    )


def downgrade() -> None:
    """Remove workflow engine persistence while retaining the prior confirmation workflow."""
    op.drop_index(
        "ix_workflow_command_receipts_workflow_id", table_name="workflow_command_receipts"
    )
    op.drop_table("workflow_command_receipts")
    op.drop_index("ix_workflow_due_timers_status", table_name="workflow_due_timers")
    op.drop_index("ix_workflow_due_timers_due_at", table_name="workflow_due_timers")
    op.drop_index("ix_workflow_due_timers_workflow_id", table_name="workflow_due_timers")
    op.drop_table("workflow_due_timers")
    op.drop_index(
        "ix_workflow_transition_history_occurred_at", table_name="workflow_transition_history"
    )
    op.drop_index(
        "ix_workflow_transition_history_command_id", table_name="workflow_transition_history"
    )
    op.drop_index(
        "ix_workflow_transition_history_workflow_id", table_name="workflow_transition_history"
    )
    op.drop_table("workflow_transition_history")
    op.drop_constraint("uq_alert_workflow_effect", "alerts", type_="unique")
    op.drop_index("ix_alerts_workflow_id", table_name="alerts")
    op.drop_constraint("fk_alerts_workflow_id", "alerts", type_="foreignkey")
    op.drop_column("alerts", "workflow_effect")
    op.drop_column("alerts", "workflow_command_id")
    op.drop_column("alerts", "workflow_id")
    op.drop_constraint("uq_clinical_task_workflow_effect", "clinical_tasks", type_="unique")
    op.drop_column("clinical_tasks", "workflow_effect")
    op.drop_column("clinical_tasks", "workflow_command_id")
    op.drop_index("ix_clinical_workflows_current_state", table_name="clinical_workflows")
    op.drop_column("clinical_workflows", "last_transition_at")
    op.drop_column("clinical_workflows", "facts")
    op.drop_column("clinical_workflows", "current_state")
    op.drop_column("clinical_workflows", "demonstration_notice")
    op.drop_column("clinical_workflows", "definition_version")
    op.drop_column("clinical_workflows", "definition_id")
    op.execute("DROP TYPE IF EXISTS workflow_due_timer_status")
    op.execute("DROP TYPE IF EXISTS workflow_state")
