"""Add R6 operational task and alert lifecycle persistence.

Revision ID: a9e6c4d2b781
Revises: f8d4b02c7a53
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a9e6c4d2b781"
down_revision: str | None = "f8d4b02c7a53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for value in ("PENDING", "ASSIGNED", "ACKNOWLEDGED", "IN_PROGRESS", "OVERDUE"):
        op.execute(f"ALTER TYPE task_status ADD VALUE IF NOT EXISTS '{value}'")

    priority = postgresql.ENUM("ROUTINE", "PRIORITY", "URGENT", name="clinical_task_priority")
    priority.create(op.get_bind(), checkfirst=True)
    priority_column = postgresql.ENUM(
        "ROUTINE", "PRIORITY", "URGENT", name="clinical_task_priority", create_type=False
    )

    op.add_column(
        "clinical_tasks",
        sa.Column("originating_decision_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "clinical_tasks",
        sa.Column("source_type", sa.String(80), nullable=False, server_default="legacy"),
    )
    op.add_column("clinical_tasks", sa.Column("source_id", sa.Uuid(), nullable=True))
    op.add_column(
        "clinical_tasks",
        sa.Column("priority", priority_column, nullable=False, server_default="ROUTINE"),
    )
    op.add_column(
        "clinical_tasks", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column("clinical_tasks", sa.Column("created_by", sa.Uuid(), nullable=True))
    op.add_column("clinical_tasks", sa.Column("acknowledged_at", sa.DateTime(timezone=True)))
    op.add_column("clinical_tasks", sa.Column("acknowledged_by", sa.Uuid(), nullable=True))
    op.add_column("clinical_tasks", sa.Column("started_at", sa.DateTime(timezone=True)))
    op.add_column("clinical_tasks", sa.Column("started_by", sa.Uuid(), nullable=True))
    op.add_column("clinical_tasks", sa.Column("cancelled_at", sa.DateTime(timezone=True)))
    op.add_column("clinical_tasks", sa.Column("cancelled_by", sa.Uuid(), nullable=True))
    op.add_column("clinical_tasks", sa.Column("cancellation_reason", sa.Text(), nullable=True))
    op.add_column("clinical_tasks", sa.Column("overdue_at", sa.DateTime(timezone=True)))
    op.add_column(
        "clinical_tasks",
        sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_clinical_task_originating_decision",
        "clinical_tasks",
        "clinical_reasoning_decisions",
        ["originating_decision_id"],
        ["decision_id"],
        ondelete="RESTRICT",
    )
    for column in ("created_by", "acknowledged_by", "started_by", "cancelled_by"):
        op.create_foreign_key(
            f"fk_clinical_task_{column}",
            "clinical_tasks",
            "clinical_users",
            [column],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_clinical_tasks_originating_decision_id",
        "clinical_tasks",
        ["originating_decision_id"],
    )
    op.create_index("ix_clinical_tasks_source_id", "clinical_tasks", ["source_id"])
    op.create_unique_constraint(
        "uq_clinical_task_case_source",
        "clinical_tasks",
        ["case_id", "source_type", "source_id"],
    )

    task_status = postgresql.ENUM(name="task_status", create_type=False)
    op.create_table(
        "clinical_task_transitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "task_id",
            sa.Uuid(),
            sa.ForeignKey("clinical_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", task_status, nullable=False),
        sa.Column("to_status", task_status, nullable=False),
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("clinical_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_clinical_task_transitions_task_id", "clinical_task_transitions", ["task_id"]
    )
    op.create_index(
        "ix_clinical_task_transitions_actor_id", "clinical_task_transitions", ["actor_id"]
    )
    op.create_index(
        "ix_clinical_task_transitions_occurred_at",
        "clinical_task_transitions",
        ["occurred_at"],
    )

    op.add_column("alerts", sa.Column("task_id", sa.Uuid(), nullable=True))
    op.add_column("alerts", sa.Column("deduplication_key", sa.String(240), nullable=True))
    op.add_column("alerts", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(
        "alerts", sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="0")
    )
    op.create_foreign_key(
        "fk_alert_task", "alerts", "clinical_tasks", ["task_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_alerts_task_id", "alerts", ["task_id"])
    op.create_unique_constraint("uq_alert_deduplication_key", "alerts", ["deduplication_key"])

    alert_status = postgresql.ENUM(name="alert_status", create_type=False)
    op.create_table(
        "clinical_alert_transitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "alert_id",
            sa.Uuid(),
            sa.ForeignKey("alerts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", alert_status, nullable=False),
        sa.Column("to_status", alert_status, nullable=False),
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("clinical_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_clinical_alert_transitions_alert_id", "clinical_alert_transitions", ["alert_id"]
    )
    op.create_index(
        "ix_clinical_alert_transitions_actor_id", "clinical_alert_transitions", ["actor_id"]
    )
    op.create_index(
        "ix_clinical_alert_transitions_occurred_at",
        "clinical_alert_transitions",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_clinical_alert_transitions_occurred_at", table_name="clinical_alert_transitions"
    )
    op.drop_index(
        "ix_clinical_alert_transitions_actor_id", table_name="clinical_alert_transitions"
    )
    op.drop_index(
        "ix_clinical_alert_transitions_alert_id", table_name="clinical_alert_transitions"
    )
    op.drop_table("clinical_alert_transitions")
    op.drop_constraint("uq_alert_deduplication_key", "alerts", type_="unique")
    op.drop_index("ix_alerts_task_id", table_name="alerts")
    op.drop_constraint("fk_alert_task", "alerts", type_="foreignkey")
    for column in ("escalation_level", "version", "deduplication_key", "task_id"):
        op.drop_column("alerts", column)

    op.drop_index(
        "ix_clinical_task_transitions_occurred_at", table_name="clinical_task_transitions"
    )
    op.drop_index(
        "ix_clinical_task_transitions_actor_id", table_name="clinical_task_transitions"
    )
    op.drop_index(
        "ix_clinical_task_transitions_task_id", table_name="clinical_task_transitions"
    )
    op.drop_table("clinical_task_transitions")
    op.drop_constraint("uq_clinical_task_case_source", "clinical_tasks", type_="unique")
    op.drop_index("ix_clinical_tasks_source_id", table_name="clinical_tasks")
    op.drop_index("ix_clinical_tasks_originating_decision_id", table_name="clinical_tasks")
    for column in ("created_by", "acknowledged_by", "started_by", "cancelled_by"):
        op.drop_constraint(f"fk_clinical_task_{column}", "clinical_tasks", type_="foreignkey")
    op.drop_constraint(
        "fk_clinical_task_originating_decision", "clinical_tasks", type_="foreignkey"
    )
    for column in (
        "escalation_level",
        "overdue_at",
        "cancellation_reason",
        "cancelled_by",
        "cancelled_at",
        "started_by",
        "started_at",
        "acknowledged_by",
        "acknowledged_at",
        "created_by",
        "version",
        "priority",
        "source_id",
        "source_type",
        "originating_decision_id",
    ):
        op.drop_column("clinical_tasks", column)
    op.execute("DROP TYPE IF EXISTS clinical_task_priority")
