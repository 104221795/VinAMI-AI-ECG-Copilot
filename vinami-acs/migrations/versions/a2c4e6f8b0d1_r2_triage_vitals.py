"""R2 append-only triage and vital documentation.

Revision ID: a2c4e6f8b0d1
Revises: f19c7a42d8e1
Create Date: 2026-07-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a2c4e6f8b0d1"
down_revision = "f19c7a42d8e1"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    """Add immutable documentation revisions and explicit-unit measurements."""
    op.create_table(
        "triage_assessments",
        sa.Column("id", UUID, nullable=False),
        sa.Column("clinical_case_id", UUID, nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("recorded_by_actor_id", UUID, nullable=False),
        sa.Column("recorded_by_actor_role", sa.String(80), nullable=False),
        sa.Column("occurred_at", UTC, nullable=False),
        sa.Column("recorded_at", UTC, nullable=False),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("causation_id", UUID, nullable=True),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("chief_complaint", sa.Text(), nullable=True),
        sa.Column("symptom_onset_state", sa.String(40), nullable=False),
        sa.Column("symptom_onset_at", UTC, nullable=True),
        sa.Column("symptom_onset_precision", sa.String(40), nullable=True),
        sa.Column("symptom_description", sa.Text(), nullable=True),
        sa.Column("symptom_location", sa.Text(), nullable=True),
        sa.Column("symptom_radiation", sa.Text(), nullable=True),
        sa.Column("symptom_duration", sa.String(500), nullable=True),
        sa.Column("symptom_pattern", sa.String(1000), nullable=True),
        sa.Column("aggravating_factors", sa.Text(), nullable=True),
        sa.Column("relieving_factors", sa.Text(), nullable=True),
        sa.Column("relevant_history_summary", sa.Text(), nullable=True),
        sa.Column("current_medication_summary", sa.Text(), nullable=True),
        sa.Column("allergy_summary", sa.Text(), nullable=True),
        sa.Column("clinical_note", sa.Text(), nullable=True),
        sa.Column("corrects_assessment_id", UUID, nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["clinical_case_id"], ["clinical_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["recorded_by_actor_id"], ["clinical_users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["corrects_assessment_id"], ["triage_assessments.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinical_case_id", "revision_number", name="uq_triage_case_revision"),
    )
    op.create_index(
        "ix_triage_assessments_clinical_case_id", "triage_assessments", ["clinical_case_id"]
    )
    op.create_index(
        "ix_triage_case_recorded", "triage_assessments", ["clinical_case_id", "recorded_at"]
    )
    op.create_index(
        "ix_triage_assessments_recorded_by_actor_id", "triage_assessments", ["recorded_by_actor_id"]
    )
    op.create_index(
        "ix_triage_assessments_correlation_id", "triage_assessments", ["correlation_id"]
    )
    op.create_index(
        "ix_triage_assessments_corrects_assessment_id",
        "triage_assessments",
        ["corrects_assessment_id"],
    )
    op.create_index("ix_triage_assessments_occurred_at", "triage_assessments", ["occurred_at"])
    op.create_index("ix_triage_assessments_recorded_at", "triage_assessments", ["recorded_at"])

    op.create_table(
        "triage_structured_observations",
        sa.Column("id", UUID, nullable=False),
        sa.Column("triage_assessment_id", UUID, nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["triage_assessment_id"], ["triage_assessments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "triage_assessment_id",
            "category",
            "name",
            name="uq_triage_observation_name",
        ),
    )
    op.create_index(
        "ix_triage_structured_observations_triage_assessment_id",
        "triage_structured_observations",
        ["triage_assessment_id"],
    )

    op.create_table(
        "vital_observation_sets",
        sa.Column("id", UUID, nullable=False),
        sa.Column("clinical_case_id", UUID, nullable=False),
        sa.Column("encounter_id", UUID, nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("device_reference", sa.String(500), nullable=True),
        sa.Column("recorded_by_actor_id", UUID, nullable=False),
        sa.Column("recorded_by_actor_role", sa.String(80), nullable=False),
        sa.Column("observed_at", UTC, nullable=False),
        sa.Column("recorded_at", UTC, nullable=False),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("causation_id", UUID, nullable=True),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("supplemental_oxygen_state", sa.String(40), nullable=False),
        sa.Column("oxygen_delivery_method", sa.String(500), nullable=True),
        sa.Column("level_of_consciousness", sa.String(1000), nullable=True),
        sa.Column("observation_note", sa.Text(), nullable=True),
        sa.Column("corrects_vital_set_id", UUID, nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["clinical_case_id"], ["clinical_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["recorded_by_actor_id"], ["clinical_users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["corrects_vital_set_id"], ["vital_observation_sets.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "clinical_case_id",
            "sequence_number",
            "revision_number",
            name="uq_vital_case_sequence_revision",
        ),
    )
    op.create_index(
        "ix_vital_observation_sets_clinical_case_id", "vital_observation_sets", ["clinical_case_id"]
    )
    op.create_index(
        "ix_vital_observation_sets_encounter_id", "vital_observation_sets", ["encounter_id"]
    )
    op.create_index(
        "ix_vital_set_case_observed",
        "vital_observation_sets",
        ["clinical_case_id", "observed_at"],
    )
    op.create_index(
        "ix_vital_observation_sets_observed_at", "vital_observation_sets", ["observed_at"]
    )
    op.create_index(
        "ix_vital_observation_sets_recorded_at", "vital_observation_sets", ["recorded_at"]
    )
    op.create_index(
        "ix_vital_observation_sets_recorded_by_actor_id",
        "vital_observation_sets",
        ["recorded_by_actor_id"],
    )
    op.create_index(
        "ix_vital_observation_sets_correlation_id", "vital_observation_sets", ["correlation_id"]
    )
    op.create_index(
        "ix_vital_observation_sets_corrects_vital_set_id",
        "vital_observation_sets",
        ["corrects_vital_set_id"],
    )

    op.create_table(
        "vital_measurements",
        sa.Column("id", UUID, nullable=False),
        sa.Column("vital_set_id", UUID, nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("observed_at", UTC, nullable=False),
        sa.Column("quality_status", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(
            ["vital_set_id"], ["vital_observation_sets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vital_set_id", "kind", name="uq_vital_measurement_kind"),
    )
    op.create_index("ix_vital_measurements_vital_set_id", "vital_measurements", ["vital_set_id"])


def downgrade() -> None:
    """Remove only the additive R2 documentation schema."""
    op.drop_index("ix_vital_measurements_vital_set_id", table_name="vital_measurements")
    op.drop_table("vital_measurements")
    for index in (
        "ix_vital_observation_sets_corrects_vital_set_id",
        "ix_vital_observation_sets_correlation_id",
        "ix_vital_observation_sets_recorded_by_actor_id",
        "ix_vital_observation_sets_recorded_at",
        "ix_vital_observation_sets_observed_at",
        "ix_vital_set_case_observed",
        "ix_vital_observation_sets_encounter_id",
        "ix_vital_observation_sets_clinical_case_id",
    ):
        op.drop_index(index, table_name="vital_observation_sets")
    op.drop_table("vital_observation_sets")
    op.drop_index(
        "ix_triage_structured_observations_triage_assessment_id",
        table_name="triage_structured_observations",
    )
    op.drop_table("triage_structured_observations")
    for index in (
        "ix_triage_assessments_recorded_at",
        "ix_triage_assessments_occurred_at",
        "ix_triage_assessments_corrects_assessment_id",
        "ix_triage_assessments_correlation_id",
        "ix_triage_assessments_recorded_by_actor_id",
        "ix_triage_case_recorded",
        "ix_triage_assessments_clinical_case_id",
    ):
        op.drop_index(index, table_name="triage_assessments")
    op.drop_table("triage_assessments")
