"""r0 safety, provenance, audit, and runtime integrity

Revision ID: a7d3f0b2c6e1
Revises: f5a9c2d6e4b1
Create Date: 2026-07-13 17:40:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import vinami.shared.persistence

revision = "a7d3f0b2c6e1"
down_revision = "f5a9c2d6e4b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the R0 safety/runtime schema as one reversible revision."""
    decision_type = postgresql.ENUM(
        "PATHWAY_ACCEPTED",
        "CATH_LAB_REVIEW_REQUESTED",
        "TRANSFER_REVIEW_REQUESTED",
        "DISCHARGE_REVIEW_APPROVED",
        "CASE_CLOSURE_APPROVED",
        name="physician_decision_type",
    )
    decision_status = postgresql.ENUM(
        "ACTIVE", "CORRECTION", "REVOKED", name="physician_decision_status"
    )
    decision_type.create(op.get_bind(), checkfirst=True)
    decision_status.create(op.get_bind(), checkfirst=True)
    decision_type_column = postgresql.ENUM(name="physician_decision_type", create_type=False)
    decision_status_column = postgresql.ENUM(name="physician_decision_status", create_type=False)

    op.create_table(
        "physician_decisions",
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("clinical_case_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("actor_role", sa.String(80), nullable=False),
        sa.Column("decision_type", decision_type_column, nullable=False),
        sa.Column("decision_status", decision_status_column, nullable=False),
        sa.Column("reason_code", sa.String(160), nullable=False),
        sa.Column("note", sa.String(4000), nullable=True),
        sa.Column("evidence_snapshot_reference", sa.String(2000), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("aggregate_expected_version", sa.Integer(), nullable=False),
        sa.Column(
            "occurred_at", vinami.shared.persistence.UTCDateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "recorded_at", vinami.shared.persistence.UTCDateTime(timezone=True), nullable=False
        ),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("causation_id", sa.Uuid(), nullable=True),
        sa.Column("corrects_decision_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["clinical_users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["clinical_case_id"], ["clinical_cases.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["corrects_decision_id"],
            ["physician_decisions.decision_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("decision_id"),
        sa.UniqueConstraint(
            "clinical_case_id",
            "correlation_id",
            "decision_type",
            name="uq_physician_decision_idempotency",
        ),
    )
    for column in (
        "actor_id",
        "clinical_case_id",
        "correlation_id",
        "causation_id",
        "decision_type",
        "decision_status",
        "occurred_at",
        "recorded_at",
    ):
        op.create_index(f"ix_physician_decisions_{column}", "physician_decisions", [column])

    op.drop_constraint(
        "clinical_workflows_decision_actor_id_fkey", "clinical_workflows", type_="foreignkey"
    )
    for column in (
        "decision_actor_id",
        "decision",
        "decision_rationale",
        "decision_recorded_at",
    ):
        op.drop_column("clinical_workflows", column)
    op.add_column(
        "clinical_workflows", sa.Column("physician_decision_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_clinical_workflows_physician_decision",
        "clinical_workflows",
        "physician_decisions",
        ["physician_decision_id"],
        ["decision_id"],
        ondelete="RESTRICT",
    )
    op.execute(
        "UPDATE clinical_workflows SET facts = facts - 'physician_decision_recorded' "
        "WHERE facts ? 'physician_decision_recorded'"
    )
    op.add_column(
        "workflow_transition_history", sa.Column("actor_role", sa.String(80), nullable=True)
    )

    op.add_column("clinical_cases", sa.Column("closure_actor_role", sa.String(80), nullable=True))
    op.add_column("clinical_cases", sa.Column("closure_command_id", sa.Uuid(), nullable=True))
    op.add_column("clinical_cases", sa.Column("closure_decision_id", sa.Uuid(), nullable=True))
    op.add_column("clinical_cases", sa.Column("disposition_outcome_id", sa.Uuid(), nullable=True))
    op.create_unique_constraint(
        "uq_clinical_case_closure_command", "clinical_cases", ["closure_command_id"]
    )
    op.create_foreign_key(
        "fk_clinical_cases_closed_by",
        "clinical_cases",
        "clinical_users",
        ["closed_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_clinical_cases_closure_decision",
        "clinical_cases",
        "physician_decisions",
        ["closure_decision_id"],
        ["decision_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_clinical_cases_disposition_outcome",
        "clinical_cases",
        "outcomes",
        ["disposition_outcome_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.add_column("ecg_ai_results", sa.Column("provider_name", sa.String(200), nullable=True))
    op.execute("UPDATE ecg_ai_results SET provider_name = 'unspecified'")
    op.alter_column("ecg_ai_results", "provider_name", nullable=False)

    lab_columns = (
        sa.Column("assay_manufacturer", sa.String(200), nullable=True),
        sa.Column("analyzer", sa.String(200), nullable=True),
        sa.Column("reference_limit", sa.Float(), nullable=True),
        sa.Column("reference_metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "ingested_at", vinami.shared.persistence.UTCDateTime(timezone=True), nullable=True
        ),
        sa.Column("source_system", sa.String(200), nullable=True),
        sa.Column("source_record_id", sa.String(300), nullable=True),
        sa.Column("quality_flags", postgresql.JSONB(), nullable=True),
        sa.Column("renal_function_context", sa.String(2000), nullable=True),
    )
    for column in lab_columns:
        op.add_column("lab_results", column)
    op.execute(
        "UPDATE lab_results SET assay_manufacturer='unspecified', analyzer='unspecified', "
        "reference_limit=1.0, reference_metadata='{}'::jsonb, source_system='unspecified', "
        "quality_flags='{\"values\": []}'::jsonb"
    )
    for column in (
        "assay_manufacturer",
        "analyzer",
        "reference_limit",
        "reference_metadata",
        "source_system",
        "quality_flags",
    ):
        op.alter_column("lab_results", column, nullable=False)

    audit_columns = (
        sa.Column("actor_role", sa.String(80), nullable=True),
        sa.Column("prior_version", sa.Integer(), nullable=True),
        sa.Column("resulting_version", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(2000), nullable=True),
        sa.Column("correlation_id", sa.Uuid(), nullable=True),
        sa.Column("causation_id", sa.Uuid(), nullable=True),
        sa.Column("outcome", sa.String(40), nullable=True),
    )
    for column in audit_columns:
        op.add_column("audit_logs", column)
    op.execute(
        "UPDATE audit_logs SET correlation_id = "
        "COALESCE(NULLIF(payload->>'correlation_id', '')::uuid, "
        "'00000000-0000-0000-0000-000000000000'::uuid), outcome='success'"
    )
    op.alter_column("audit_logs", "correlation_id", nullable=False)
    op.alter_column("audit_logs", "outcome", nullable=False)
    op.create_index("ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"])
    op.create_index("ix_audit_logs_causation_id", "audit_logs", ["causation_id"])

    op.execute(
        """
        CREATE FUNCTION prevent_audit_log_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs are append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation();
        """
    )


def downgrade() -> None:
    """Remove R0 schema additions and restore the legacy decision columns."""
    op.execute("DROP TRIGGER IF EXISTS audit_logs_immutable ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mutation()")
    op.drop_index("ix_audit_logs_causation_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_correlation_id", table_name="audit_logs")
    for column in (
        "outcome",
        "causation_id",
        "correlation_id",
        "reason",
        "resulting_version",
        "prior_version",
        "actor_role",
    ):
        op.drop_column("audit_logs", column)

    for column in (
        "renal_function_context",
        "quality_flags",
        "source_record_id",
        "source_system",
        "ingested_at",
        "reference_metadata",
        "reference_limit",
        "analyzer",
        "assay_manufacturer",
    ):
        op.drop_column("lab_results", column)
    op.drop_column("ecg_ai_results", "provider_name")

    op.drop_constraint(
        "fk_clinical_cases_disposition_outcome", "clinical_cases", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_clinical_cases_closure_decision", "clinical_cases", type_="foreignkey"
    )
    op.drop_constraint("fk_clinical_cases_closed_by", "clinical_cases", type_="foreignkey")
    op.drop_constraint("uq_clinical_case_closure_command", "clinical_cases", type_="unique")
    for column in (
        "disposition_outcome_id",
        "closure_decision_id",
        "closure_command_id",
        "closure_actor_role",
    ):
        op.drop_column("clinical_cases", column)

    op.drop_column("workflow_transition_history", "actor_role")
    op.drop_constraint(
        "fk_clinical_workflows_physician_decision", "clinical_workflows", type_="foreignkey"
    )
    op.drop_column("clinical_workflows", "physician_decision_id")
    op.add_column(
        "clinical_workflows", sa.Column("decision_recorded_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "clinical_workflows", sa.Column("decision_rationale", sa.String(4000), nullable=True)
    )
    op.add_column("clinical_workflows", sa.Column("decision", sa.String(200), nullable=True))
    op.add_column("clinical_workflows", sa.Column("decision_actor_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "clinical_workflows_decision_actor_id_fkey",
        "clinical_workflows",
        "clinical_users",
        ["decision_actor_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    for column in (
        "recorded_at",
        "occurred_at",
        "decision_status",
        "decision_type",
        "causation_id",
        "correlation_id",
        "clinical_case_id",
        "actor_id",
    ):
        op.drop_index(f"ix_physician_decisions_{column}", table_name="physician_decisions")
    op.drop_table("physician_decisions")
    op.execute("DROP TYPE IF EXISTS physician_decision_status")
    op.execute("DROP TYPE IF EXISTS physician_decision_type")

