"""Complete R3 hospital ingestion, Dynamic ECG review, and repeat ECG lifecycle.

Revision ID: c8a4e7f2d913
Revises: b7f3a9d1e6c2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from vinami.shared.persistence import UTCDateTime

revision: str = "c8a4e7f2d913"
down_revision: str | None = "b7f3a9d1e6c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ecg_ingestion_jobs",
        sa.Column("requested_by_role", sa.String(80), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "ecg_ingestion_jobs",
        sa.Column("request_source", sa.String(160), nullable=False, server_default="legacy"),
    )
    op.add_column(
        "ecg_ingestion_jobs",
        sa.Column("idempotency_key", sa.String(240), nullable=False, server_default="legacy"),
    )
    op.add_column(
        "ecg_ingestion_jobs",
        sa.Column("study_reference", sa.String(240), nullable=False, server_default="legacy"),
    )
    op.add_column("ecg_ingestion_jobs", sa.Column("acquisition_at", UTCDateTime(), nullable=True))
    op.execute("UPDATE ecg_ingestion_jobs SET acquisition_at = requested_at")
    op.alter_column("ecg_ingestion_jobs", "acquisition_at", nullable=False)
    op.add_column(
        "ecg_ingestion_jobs",
        sa.Column(
            "content_type", sa.String(160), nullable=False, server_default="application/octet-stream"
        ),
    )
    op.add_column("ecg_ingestion_jobs", sa.Column("retry_of_job_id", UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_ecg_ingestion_retry_of",
        "ecg_ingestion_jobs",
        "ecg_ingestion_jobs",
        ["retry_of_job_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.add_column(
        "dynamic_ecg_comparisons",
        sa.Column("requested_by_role", sa.String(80), nullable=False, server_default="unknown"),
    )
    op.add_column("dynamic_ecg_comparisons", sa.Column("started_at", UTCDateTime()))
    op.add_column(
        "dynamic_ecg_comparisons",
        sa.Column(
            "physician_review_status", sa.String(40), nullable=False, server_default="pending"
        ),
    )
    op.add_column(
        "dynamic_ecg_comparisons",
        sa.Column(
            "model_score_compatibility",
            sa.String(80),
            nullable=False,
            server_default="not_available",
        ),
    )

    op.create_table(
        "dynamic_ecg_physician_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("comparison_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_role", sa.String(80), nullable=False),
        sa.Column("review_status", sa.String(80), nullable=False),
        sa.Column("interpretation", sa.Text(), nullable=False),
        sa.Column("occurred_at", UTCDateTime(), nullable=False),
        sa.Column("recorded_at", UTCDateTime(), nullable=False),
        sa.Column("correlation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("supersedes_review_id", UUID(as_uuid=True)),
        sa.Column("correction_reason", sa.Text()),
        sa.ForeignKeyConstraint(
            ["comparison_id"], ["dynamic_ecg_comparisons.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["clinical_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["supersedes_review_id"],
            ["dynamic_ecg_physician_reviews.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("comparison_id", "revision_number", name="uq_dynamic_review_revision"),
    )
    op.create_index(
        "ix_dynamic_ecg_physician_reviews_comparison_id",
        "dynamic_ecg_physician_reviews",
        ["comparison_id"],
    )
    op.create_index(
        "ix_dynamic_ecg_physician_reviews_correlation_id",
        "dynamic_ecg_physician_reviews",
        ["correlation_id"],
    )

    op.add_column(
        "ecg_repeat_reminders",
        sa.Column("requested_by_role", sa.String(80), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "ecg_repeat_reminders",
        sa.Column("origin", sa.String(80), nullable=False, server_default="physician_request"),
    )
    op.add_column("ecg_repeat_reminders", sa.Column("completed_at", UTCDateTime()))
    op.add_column("ecg_repeat_reminders", sa.Column("cancelled_by", UUID(as_uuid=True)))
    op.add_column("ecg_repeat_reminders", sa.Column("cancelled_at", UTCDateTime()))
    op.add_column("ecg_repeat_reminders", sa.Column("cancellation_reason", sa.Text()))
    op.add_column("ecg_repeat_reminders", sa.Column("updated_at", UTCDateTime(), nullable=True))
    op.execute("UPDATE ecg_repeat_reminders SET updated_at = created_at")
    op.alter_column("ecg_repeat_reminders", "updated_at", nullable=False)
    op.create_foreign_key(
        "fk_ecg_repeat_reminder_cancelled_by",
        "ecg_repeat_reminders",
        "clinical_users",
        ["cancelled_by"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ecg_repeat_reminder_cancelled_by", "ecg_repeat_reminders", type_="foreignkey"
    )
    for column in (
        "updated_at",
        "cancellation_reason",
        "cancelled_at",
        "cancelled_by",
        "completed_at",
        "origin",
        "requested_by_role",
    ):
        op.drop_column("ecg_repeat_reminders", column)
    op.drop_table("dynamic_ecg_physician_reviews")
    for column in (
        "model_score_compatibility",
        "physician_review_status",
        "started_at",
        "requested_by_role",
    ):
        op.drop_column("dynamic_ecg_comparisons", column)
    op.drop_constraint("fk_ecg_ingestion_retry_of", "ecg_ingestion_jobs", type_="foreignkey")
    for column in (
        "retry_of_job_id",
        "content_type",
        "acquisition_at",
        "study_reference",
        "idempotency_key",
        "request_source",
        "requested_by_role",
    ):
        op.drop_column("ecg_ingestion_jobs", column)
