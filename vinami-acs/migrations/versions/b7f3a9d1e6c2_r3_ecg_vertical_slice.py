"""R3 ECG Intelligence, ingestion, review, and dynamic comparison.

Revision ID: b7f3a9d1e6c2
Revises: a2c4e6f8b0d1
Create Date: 2026-07-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b7f3a9d1e6c2"
down_revision = "a2c4e6f8b0d1"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
UTC = sa.DateTime(timezone=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "ecg_artifacts",
        sa.Column("id", UUID, nullable=False),
        sa.Column("artifact_kind", sa.String(80), nullable=False),
        sa.Column("content_type", sa.String(160), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.CheckConstraint("size_bytes > 0", name="ck_ecg_artifact_positive_size"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ecg_artifacts_artifact_kind", "ecg_artifacts", ["artifact_kind"])
    op.create_index("ix_ecg_artifacts_checksum_sha256", "ecg_artifacts", ["checksum_sha256"])
    op.create_index("ix_ecg_artifacts_created_at", "ecg_artifacts", ["created_at"])

    op.create_table(
        "ecg_study_details",
        sa.Column("study_id", UUID, nullable=False),
        sa.Column("clinical_case_id", UUID, nullable=False),
        sa.Column("encounter_id", UUID, nullable=False),
        sa.Column("study_reference", sa.String(240), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_system", sa.String(240), nullable=False),
        sa.Column("source_connector_id", sa.String(240), nullable=True),
        sa.Column("acquisition_device", sa.String(500), nullable=True),
        sa.Column("acquisition_at", UTC, nullable=False),
        sa.Column("ingestion_at", UTC, nullable=False),
        sa.Column("study_status", sa.String(40), nullable=False),
        sa.Column("lead_configuration", sa.String(240), nullable=False),
        sa.Column("sampling_rate_hz", sa.Float(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("amplitude_unit", sa.String(40), nullable=True),
        sa.Column("raw_artifact_id", UUID, nullable=False),
        sa.Column("normalized_waveform_artifact_id", UUID, nullable=True),
        sa.Column("preview_artifact_id", UUID, nullable=True),
        sa.Column("source_format", sa.String(160), nullable=False),
        sa.Column("source_content_type", sa.String(160), nullable=False),
        sa.Column("artifact_checksum", sa.String(64), nullable=False),
        sa.Column("artifact_size", sa.Integer(), nullable=False),
        sa.Column("parser_version", sa.String(120), nullable=False),
        sa.Column("preprocessing_version", sa.String(120), nullable=True),
        sa.Column("quality_status", sa.String(40), nullable=False),
        sa.Column("created_by_actor_id", UUID, nullable=False),
        sa.Column("created_by_actor_role", sa.String(80), nullable=False),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.Column("waveform_available", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["study_id"], ["ecg_studies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["clinical_case_id"], ["clinical_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["raw_artifact_id"], ["ecg_artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["normalized_waveform_artifact_id"], ["ecg_artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["preview_artifact_id"], ["ecg_artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_actor_id"], ["clinical_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("study_id"),
        sa.UniqueConstraint("study_reference", name="uq_ecg_study_reference"),
    )
    op.create_index("ix_ecg_study_case_acquired", "ecg_study_details", ["clinical_case_id", "acquisition_at"])
    op.create_index("ix_ecg_study_details_encounter_id", "ecg_study_details", ["encounter_id"])
    op.create_index("ix_ecg_study_details_source_type", "ecg_study_details", ["source_type"])
    op.create_index("ix_ecg_study_details_correlation_id", "ecg_study_details", ["correlation_id"])

    op.create_table(
        "ecg_waveform_metadata",
        sa.Column("study_id", UUID, nullable=False),
        sa.Column("document", JSONB, nullable=False),
        sa.ForeignKeyConstraint(["study_id"], ["ecg_studies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("study_id"),
    )
    op.create_table(
        "ecg_quality_assessments",
        sa.Column("id", UUID, nullable=False),
        sa.Column("study_id", UUID, nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("reason_codes", JSONB, nullable=False),
        sa.Column("affected_leads", JSONB, nullable=False),
        sa.Column("parser_warnings", JSONB, nullable=False),
        sa.Column("preprocessing_warnings", JSONB, nullable=False),
        sa.Column("engine_version", sa.String(120), nullable=False),
        sa.Column("assessed_at", UTC, nullable=False),
        sa.ForeignKeyConstraint(["study_id"], ["ecg_studies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_id"),
    )
    op.create_index("ix_ecg_quality_assessments_study_id", "ecg_quality_assessments", ["study_id"])
    op.create_index("ix_ecg_quality_assessments_status", "ecg_quality_assessments", ["status"])

    op.create_table(
        "ecg_ingestion_jobs",
        sa.Column("id", UUID, nullable=False),
        sa.Column("clinical_case_id", UUID, nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_connector_id", sa.String(240), nullable=True),
        sa.Column("external_reference", sa.String(500), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("requested_by", UUID, nullable=False),
        sa.Column("requested_at", UTC, nullable=False),
        sa.Column("started_at", UTC, nullable=True),
        sa.Column("completed_at", UTC, nullable=True),
        sa.Column("artifact_id", UUID, nullable=True),
        sa.Column("resulting_study_id", UUID, nullable=True),
        sa.Column("parser_name", sa.String(160), nullable=True),
        sa.Column("parser_version", sa.String(120), nullable=True),
        sa.Column("warnings", JSONB, nullable=False),
        sa.Column("failure_category", sa.String(120), nullable=True),
        sa.Column("failure_detail_safe", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["clinical_case_id"], ["clinical_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["clinical_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["artifact_id"], ["ecg_artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resulting_study_id"], ["ecg_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ecg_ingestion_case_requested", "ecg_ingestion_jobs", ["clinical_case_id", "requested_at"])
    op.create_index("ix_ecg_ingestion_jobs_status", "ecg_ingestion_jobs", ["status"])
    op.create_index("ix_ecg_ingestion_jobs_correlation_id", "ecg_ingestion_jobs", ["correlation_id"])

    op.create_table(
        "ecg_ai_analyses",
        sa.Column("id", UUID, nullable=False),
        sa.Column("ecg_study_id", UUID, nullable=False),
        sa.Column("provider_name", sa.String(200), nullable=False),
        sa.Column("provider_version", sa.String(120), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("model_version", sa.String(120), nullable=False),
        sa.Column("model_checksum", sa.String(64), nullable=True),
        sa.Column("preprocessing_version", sa.String(120), nullable=False),
        sa.Column("label_mapping_version", sa.String(120), nullable=False),
        sa.Column("threshold_version", sa.String(200), nullable=True),
        sa.Column("input_artifact_id", UUID, nullable=False),
        sa.Column("input_artifact_checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("quality_status", sa.String(40), nullable=False),
        sa.Column("requested_by", UUID, nullable=False),
        sa.Column("requested_at", UTC, nullable=False),
        sa.Column("started_at", UTC, nullable=True),
        sa.Column("completed_at", UTC, nullable=True),
        sa.Column("inference_duration_ms", sa.Integer(), nullable=True),
        sa.Column("warnings", JSONB, nullable=False),
        sa.Column("explanation_status", sa.String(40), nullable=False),
        sa.Column("explanation_artifact_id", UUID, nullable=True),
        sa.Column("failure_category", sa.String(120), nullable=True),
        sa.Column("failure_detail_safe", sa.Text(), nullable=True),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["ecg_study_id"], ["ecg_studies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["input_artifact_id"], ["ecg_artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["explanation_artifact_id"], ["ecg_artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by"], ["clinical_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ecg_analysis_study_requested", "ecg_ai_analyses", ["ecg_study_id", "requested_at"])
    op.create_index("ix_ecg_ai_analyses_status", "ecg_ai_analyses", ["status"])
    op.create_index("ix_ecg_ai_analyses_completed_at", "ecg_ai_analyses", ["completed_at"])
    op.create_index("ix_ecg_ai_analyses_correlation_id", "ecg_ai_analyses", ["correlation_id"])

    op.create_table(
        "ecg_ai_analysis_findings",
        sa.Column("id", UUID, nullable=False),
        sa.Column("analysis_id", UUID, nullable=False),
        sa.Column("finding_code", sa.String(80), nullable=False),
        sa.Column("display_label", sa.String(240), nullable=False),
        sa.Column("model_score", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("threshold_met", sa.Boolean(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("finding_status", sa.String(80), nullable=False),
        sa.Column("explanation_reference", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(["analysis_id"], ["ecg_ai_analyses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_id", "finding_code", name="uq_ecg_analysis_finding"),
    )
    op.create_index("ix_ecg_ai_analysis_findings_analysis_id", "ecg_ai_analysis_findings", ["analysis_id"])

    op.create_table(
        "physician_ecg_interpretations",
        sa.Column("id", UUID, nullable=False),
        sa.Column("ecg_study_id", UUID, nullable=False),
        sa.Column("analysis_id", UUID, nullable=True),
        sa.Column("actor_id", UUID, nullable=False),
        sa.Column("actor_role", sa.String(80), nullable=False),
        sa.Column("interpretation_status", sa.String(80), nullable=False),
        sa.Column("structured_interpretation", sa.Text(), nullable=False),
        sa.Column("agreement_status", sa.String(80), nullable=False),
        sa.Column("disagreement_reason", sa.Text(), nullable=True),
        sa.Column("quality_disposition", sa.String(80), nullable=False),
        sa.Column("repeat_ecg_requested", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("occurred_at", UTC, nullable=False),
        sa.Column("recorded_at", UTC, nullable=False),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("supersedes_interpretation_id", UUID, nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["ecg_study_id"], ["ecg_studies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_id"], ["ecg_ai_analyses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["clinical_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_interpretation_id"], ["physician_ecg_interpretations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ecg_study_id", "revision_number", name="uq_ecg_interpretation_revision"),
    )
    op.create_index("ix_physician_ecg_interpretations_ecg_study_id", "physician_ecg_interpretations", ["ecg_study_id"])
    op.create_index("ix_physician_ecg_interpretations_correlation_id", "physician_ecg_interpretations", ["correlation_id"])

    op.create_table(
        "dynamic_ecg_comparisons",
        sa.Column("id", UUID, nullable=False),
        sa.Column("clinical_case_id", UUID, nullable=False),
        sa.Column("baseline_study_id", UUID, nullable=False),
        sa.Column("current_study_id", UUID, nullable=False),
        sa.Column("comparison_policy_version", sa.String(120), nullable=False),
        sa.Column("preprocessing_version", sa.String(120), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("comparability_status", sa.String(40), nullable=False),
        sa.Column("comparability_reasons", JSONB, nullable=False),
        sa.Column("lead_comparisons", JSONB, nullable=False),
        sa.Column("technical_change_indicators", JSONB, nullable=False),
        sa.Column("model_score_deltas", JSONB, nullable=False),
        sa.Column("quality_context", sa.Text(), nullable=False),
        sa.Column("requested_by", UUID, nullable=False),
        sa.Column("requested_at", UTC, nullable=False),
        sa.Column("completed_at", UTC, nullable=False),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.CheckConstraint("baseline_study_id <> current_study_id", name="ck_dynamic_ecg_distinct_studies"),
        sa.ForeignKeyConstraint(["clinical_case_id"], ["clinical_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["baseline_study_id"], ["ecg_studies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["current_study_id"], ["ecg_studies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by"], ["clinical_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dynamic_ecg_case_requested", "dynamic_ecg_comparisons", ["clinical_case_id", "requested_at"])
    op.create_index("ix_dynamic_ecg_comparisons_correlation_id", "dynamic_ecg_comparisons", ["correlation_id"])

    op.create_table(
        "ecg_repeat_reminders",
        sa.Column("id", UUID, nullable=False),
        sa.Column("clinical_case_id", UUID, nullable=False),
        sa.Column("source_study_id", UUID, nullable=False),
        sa.Column("requested_by", UUID, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("due_at", UTC, nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("acknowledged_by", UUID, nullable=True),
        sa.Column("acknowledged_at", UTC, nullable=True),
        sa.Column("completed_study_id", UUID, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["clinical_case_id"], ["clinical_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_study_id"], ["ecg_studies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by"], ["clinical_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["clinical_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["completed_study_id"], ["ecg_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ecg_repeat_case_due", "ecg_repeat_reminders", ["clinical_case_id", "due_at"])
    op.create_index("ix_ecg_repeat_reminders_status", "ecg_repeat_reminders", ["status"])
    op.create_index("ix_ecg_repeat_reminders_correlation_id", "ecg_repeat_reminders", ["correlation_id"])


def downgrade() -> None:
    for table in (
        "ecg_repeat_reminders",
        "dynamic_ecg_comparisons",
        "physician_ecg_interpretations",
        "ecg_ai_analysis_findings",
        "ecg_ai_analyses",
        "ecg_ingestion_jobs",
        "ecg_quality_assessments",
        "ecg_waveform_metadata",
        "ecg_study_details",
        "ecg_artifacts",
    ):
        op.drop_table(table)
