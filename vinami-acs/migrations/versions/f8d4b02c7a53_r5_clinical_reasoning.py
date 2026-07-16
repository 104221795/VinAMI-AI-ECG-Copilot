"""Add immutable R5 evidence, assessment, and physician-decision records.

Revision ID: f8d4b02c7a53
Revises: e7c3a91b6f42
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f8d4b02c7a53"
down_revision: str | None = "e7c3a91b6f42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
JSON = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "clinical_evidence_snapshots",
        sa.Column("snapshot_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "clinical_case_id",
            sa.Uuid(),
            sa.ForeignKey("clinical_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by_actor_id",
            sa.Uuid(),
            sa.ForeignKey("clinical_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sources", JSON, nullable=False),
        sa.Column("summaries", JSON, nullable=False),
        sa.Column("freshness", JSON, nullable=False),
        sa.Column("missing_evidence", JSON, nullable=False),
        sa.Column("technical_conflicts", JSON, nullable=False),
    )
    op.create_index(
        "ix_evidence_snapshot_case_created",
        "clinical_evidence_snapshots",
        ["clinical_case_id", "created_at"],
    )
    op.create_table(
        "physician_clinical_assessments",
        sa.Column("assessment_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "clinical_case_id",
            sa.Uuid(),
            sa.ForeignKey("clinical_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("clinical_evidence_snapshots.snapshot_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("supporting_evidence", JSON, nullable=False),
        sa.Column("contradictory_evidence", JSON, nullable=False),
        sa.Column("uncertainty", sa.Text(), nullable=False),
        sa.Column("additional_information_required", sa.Text(), nullable=True),
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("clinical_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_role", sa.String(80), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "corrects_assessment_id",
            sa.Uuid(),
            sa.ForeignKey("physician_clinical_assessments.assessment_id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("correction_reason", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_physician_assessment_case_revision",
        "physician_clinical_assessments",
        ["clinical_case_id", "revision_number"],
    )
    op.create_table(
        "clinical_reasoning_decisions",
        sa.Column("decision_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "clinical_case_id",
            sa.Uuid(),
            sa.ForeignKey("clinical_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("clinical_evidence_snapshots.snapshot_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assessment_id",
            sa.Uuid(),
            sa.ForeignKey("physician_clinical_assessments.assessment_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("decision_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("uncertainty", sa.Text(), nullable=False),
        sa.Column("evidence_references", JSON, nullable=False),
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("clinical_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_role", sa.String(80), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "corrects_decision_id",
            sa.Uuid(),
            sa.ForeignKey("clinical_reasoning_decisions.decision_id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column(
            "workflow_authorization_id",
            sa.Uuid(),
            sa.ForeignKey("physician_decisions.decision_id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_reasoning_decision_case_revision",
        "clinical_reasoning_decisions",
        ["clinical_case_id", "revision_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_reasoning_decision_case_revision", table_name="clinical_reasoning_decisions")
    op.drop_table("clinical_reasoning_decisions")
    op.drop_index(
        "ix_physician_assessment_case_revision", table_name="physician_clinical_assessments"
    )
    op.drop_table("physician_clinical_assessments")
    op.drop_index("ix_evidence_snapshot_case_created", table_name="clinical_evidence_snapshots")
    op.drop_table("clinical_evidence_snapshots")
