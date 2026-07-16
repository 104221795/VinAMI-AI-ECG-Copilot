"""Add R9 timeline, audit, outcome revisions and research exports.

Revision ID: b4e2d9c7a103
Revises: a9e6c4d2b781
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from vinami.shared.persistence import JSONDocument

revision: str = "b4e2d9c7a103"
down_revision: str | None = "a9e6c4d2b781"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("timeline_events", sa.Column("source_record_id", sa.Uuid(), nullable=True))
    op.add_column("timeline_events", sa.Column("source_record_version", sa.Integer()))
    op.add_column(
        "timeline_events",
        sa.Column("correction_status", sa.String(40), nullable=False, server_default="original"),
    )
    op.add_column(
        "timeline_events", sa.Column("supersedes_timeline_event_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "timeline_events", sa.Column("revokes_timeline_event_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "timeline_events",
        sa.Column(
            "data_classification", sa.String(80), nullable=False, server_default="clinical"
        ),
    )
    op.create_index("ix_timeline_events_source_record_id", "timeline_events", ["source_record_id"])
    op.create_index(
        "ix_timeline_events_correction_status", "timeline_events", ["correction_status"]
    )

    op.add_column("audit_logs", sa.Column("idempotency_key", sa.String(200), nullable=True))
    op.add_column("audit_logs", sa.Column("authorization_result", sa.String(80), nullable=True))
    op.add_column(
        "audit_logs",
        sa.Column("correction_status", sa.String(40), nullable=False, server_default="original"),
    )
    op.add_column("audit_logs", sa.Column("source_record_version", sa.Integer()))
    op.create_index("ix_audit_logs_idempotency_key", "audit_logs", ["idempotency_key"])

    op.drop_constraint("uq_outcome_case", "outcomes", type_="unique")
    op.add_column(
        "outcomes",
        sa.Column("outcome_type", sa.String(80), nullable=False, server_default="disposition"),
    )
    op.add_column("outcomes", sa.Column("outcome_timestamp", sa.DateTime(timezone=True)))
    op.add_column("outcomes", sa.Column("disposition", sa.String(240)))
    op.add_column("outcomes", sa.Column("destination", sa.String(240)))
    op.add_column("outcomes", sa.Column("final_conclusion", sa.Text()))
    op.add_column("outcomes", sa.Column("cath_lab_review_outcome", sa.Text()))
    op.add_column("outcomes", sa.Column("intervention_reference", sa.Text()))
    op.add_column("outcomes", sa.Column("complications", sa.Text()))
    op.add_column("outcomes", sa.Column("follow_up_status", sa.Text()))
    op.add_column(
        "outcomes",
        sa.Column("data_completeness", sa.String(80), nullable=False, server_default="documented"),
    )
    op.add_column(
        "outcomes",
        sa.Column(
            "source", sa.String(120), nullable=False, server_default="physician_documented"
        ),
    )
    op.add_column("outcomes", sa.Column("actor_role", sa.String(80)))
    op.add_column("outcomes", sa.Column("uncertainty", sa.Text()))
    op.add_column("outcomes", sa.Column("unavailable_reason", sa.Text()))
    op.add_column(
        "outcomes", sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "outcomes", sa.Column("record_version", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column("outcomes", sa.Column("supersedes_outcome_id", sa.Uuid()))
    op.add_column("outcomes", sa.Column("correction_reason", sa.Text()))
    op.add_column("outcomes", sa.Column("idempotency_key", sa.String(200)))
    op.add_column("outcomes", sa.Column("correlation_id", sa.Uuid()))
    op.add_column("outcomes", sa.Column("causation_id", sa.Uuid()))
    op.execute("UPDATE outcomes SET outcome_timestamp = recorded_at WHERE outcome_timestamp IS NULL")
    op.execute("UPDATE outcomes SET final_conclusion = summary WHERE final_conclusion IS NULL")
    op.create_foreign_key(
        "fk_outcomes_supersedes",
        "outcomes",
        "outcomes",
        ["supersedes_outcome_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_outcome_case_revision", "outcomes", ["case_id", "revision_number"]
    )
    op.create_index("ix_outcomes_case_revision", "outcomes", ["case_id", "revision_number"])
    op.create_index("ix_outcomes_correlation_id", "outcomes", ["correlation_id"])
    op.create_index("ix_outcomes_causation_id", "outcomes", ["causation_id"])

    op.create_table(
        "clinical_research_exports",
        sa.Column("export_id", sa.Uuid(), primary_key=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("schema_version", sa.String(80), nullable=False),
        sa.Column(
            "requested_by",
            sa.Uuid(),
            sa.ForeignKey("clinical_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("requested_by_role", sa.String(80), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("case_ids", JSONDocument, nullable=False),
        sa.Column("filters", JSONDocument, nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("pseudonymization_method", sa.String(160), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("content_json", JSONDocument, nullable=False),
        sa.Column("content_csv", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("metadata", JSONDocument, nullable=False),
        sa.UniqueConstraint(
            "requested_by", "idempotency_key", name="uq_research_export_actor_key"
        ),
    )
    op.create_index("ix_research_exports_requested", "clinical_research_exports", ["requested_at"])
    op.create_index(
        "ix_clinical_research_exports_correlation_id",
        "clinical_research_exports",
        ["correlation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_clinical_research_exports_correlation_id", table_name="clinical_research_exports"
    )
    op.drop_index("ix_research_exports_requested", table_name="clinical_research_exports")
    op.drop_table("clinical_research_exports")

    op.drop_index("ix_outcomes_causation_id", table_name="outcomes")
    op.drop_index("ix_outcomes_correlation_id", table_name="outcomes")
    op.drop_index("ix_outcomes_case_revision", table_name="outcomes")
    op.drop_constraint("uq_outcome_case_revision", "outcomes", type_="unique")
    op.drop_constraint("fk_outcomes_supersedes", "outcomes", type_="foreignkey")
    for column in (
        "causation_id",
        "correlation_id",
        "idempotency_key",
        "correction_reason",
        "supersedes_outcome_id",
        "record_version",
        "revision_number",
        "unavailable_reason",
        "uncertainty",
        "actor_role",
        "source",
        "data_completeness",
        "follow_up_status",
        "complications",
        "intervention_reference",
        "cath_lab_review_outcome",
        "final_conclusion",
        "destination",
        "disposition",
        "outcome_timestamp",
        "outcome_type",
    ):
        op.drop_column("outcomes", column)
    op.create_unique_constraint("uq_outcome_case", "outcomes", ["case_id"])

    op.drop_index("ix_audit_logs_idempotency_key", table_name="audit_logs")
    for column in (
        "source_record_version",
        "correction_status",
        "authorization_result",
        "idempotency_key",
    ):
        op.drop_column("audit_logs", column)

    op.drop_index("ix_timeline_events_correction_status", table_name="timeline_events")
    op.drop_index("ix_timeline_events_source_record_id", table_name="timeline_events")
    for column in (
        "data_classification",
        "revokes_timeline_event_id",
        "supersedes_timeline_event_id",
        "correction_status",
        "source_record_version",
        "source_record_id",
    ):
        op.drop_column("timeline_events", column)
