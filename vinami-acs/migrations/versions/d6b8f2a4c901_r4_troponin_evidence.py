"""R4 immutable serial troponin evidence and laboratory import workflow.

Revision ID: d6b8f2a4c901
Revises: c8a4e7f2d913
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d6b8f2a4c901"
down_revision: str | None = "c8a4e7f2d913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_TYPE = postgresql.UUID(as_uuid=True)
JSON = postgresql.JSONB(astext_type=sa.Text())
TZ = sa.DateTime(timezone=True)
DECIMAL = sa.Numeric(30, 10)


def upgrade() -> None:
    op.create_table(
        "troponin_assay_definitions",
        sa.Column("assay_id", UUID_TYPE, primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(240), nullable=False),
        sa.Column("analyte", sa.String(80), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("manufacturer", sa.String(160), nullable=False),
        sa.Column("platform", sa.String(160), nullable=False),
        sa.Column("assay_version", sa.String(80), nullable=False),
        sa.Column("canonical_unit", sa.String(30)),
        sa.Column("effective_version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("code", "effective_version", name="uq_trop_assay_code_version"),
    )
    op.create_index("ix_troponin_assay_definitions_code", "troponin_assay_definitions", ["code"])
    op.create_table(
        "troponin_evidence_results",
        sa.Column("result_id", UUID_TYPE, primary_key=True),
        sa.Column(
            "clinical_case_id",
            UUID_TYPE,
            sa.ForeignKey("clinical_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assay_id",
            UUID_TYPE,
            sa.ForeignKey("troponin_assay_definitions.assay_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("analyte", sa.String(80), nullable=False),
        sa.Column("original_value", DECIMAL, nullable=False),
        sa.Column("original_unit", sa.String(30), nullable=False),
        sa.Column("normalized_value", DECIMAL),
        sa.Column("normalized_unit", sa.String(30)),
        sa.Column("conversion_status", sa.String(80), nullable=False),
        sa.Column("conversion_version", sa.String(80), nullable=False),
        sa.Column("specimen_type", sa.String(80), nullable=False),
        sa.Column("specimen_collected_at", TZ, nullable=False),
        sa.Column("resulted_at", TZ, nullable=False),
        sa.Column("result_status", sa.String(40), nullable=False),
        sa.Column("reference_limit_value", DECIMAL),
        sa.Column("reference_limit_unit", sa.String(30)),
        sa.Column("reference_limit_source", sa.String(240)),
        sa.Column("quality_flags", JSON, nullable=False),
        sa.Column("source_system", sa.String(160), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_result_id", sa.String(240), nullable=False),
        sa.Column("accession_number", sa.String(160)),
        sa.Column("note", sa.String(2000)),
        sa.Column(
            "supersedes_result_id",
            UUID_TYPE,
            sa.ForeignKey("troponin_evidence_results.result_id", ondelete="RESTRICT"),
        ),
        sa.Column("amendment_reason", sa.String(1000)),
        sa.Column(
            "recorded_by_actor_id",
            UUID_TYPE,
            sa.ForeignKey("clinical_users.id", ondelete="RESTRICT"),
        ),
        sa.Column("recorded_by_role", sa.String(80), nullable=False),
        sa.Column("recorded_at", TZ, nullable=False),
        sa.Column("correlation_id", UUID_TYPE, nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("source_system", "source_result_id", name="uq_trop_source_result"),
    )
    op.create_index(
        "ix_trop_case_specimen",
        "troponin_evidence_results",
        ["clinical_case_id", "specimen_collected_at"],
    )
    op.create_index("ix_trop_accession", "troponin_evidence_results", ["accession_number"])
    op.create_index("ix_trop_result_assay", "troponin_evidence_results", ["assay_id"])
    op.create_index("ix_trop_result_status", "troponin_evidence_results", ["result_status"])
    op.create_table(
        "laboratory_import_jobs",
        sa.Column("import_job_id", UUID_TYPE, primary_key=True),
        sa.Column(
            "clinical_case_id",
            UUID_TYPE,
            sa.ForeignKey("clinical_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("connector_id", sa.String(120), nullable=False),
        sa.Column("external_reference", sa.String(240), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column(
            "requested_by_actor_id",
            UUID_TYPE,
            sa.ForeignKey("clinical_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("requested_by_actor_role", sa.String(80), nullable=False),
        sa.Column("requested_at", TZ, nullable=False),
        sa.Column("started_at", TZ),
        sa.Column("completed_at", TZ),
        sa.Column("source_message_reference", sa.String(240)),
        sa.Column("resulting_result_ids", JSON, nullable=False),
        sa.Column("parser_name", sa.String(160), nullable=False),
        sa.Column("parser_version", sa.String(40), nullable=False),
        sa.Column("warnings", JSON, nullable=False),
        sa.Column("failure_category", sa.String(80)),
        sa.Column("failure_detail_safe", sa.String(500)),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("correlation_id", UUID_TYPE, nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("clinical_case_id", "idempotency_key", name="uq_lab_import_case_key"),
    )
    op.create_index("ix_lab_import_status", "laboratory_import_jobs", ["status"])
    op.create_index("ix_lab_import_case", "laboratory_import_jobs", ["clinical_case_id"])
    op.create_index("ix_lab_import_external", "laboratory_import_jobs", ["external_reference"])
    op.create_table(
        "clinician_troponin_reviews",
        sa.Column("review_id", UUID_TYPE, primary_key=True),
        sa.Column(
            "clinical_case_id",
            UUID_TYPE,
            sa.ForeignKey("clinical_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("referenced_result_ids", JSON, nullable=False),
        sa.Column(
            "actor_id",
            UUID_TYPE,
            sa.ForeignKey("clinical_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_role", sa.String(80), nullable=False),
        sa.Column("review_status", sa.String(80), nullable=False),
        sa.Column("incompatibility_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("quality_limitation_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("repeat_measurement_requested", sa.Boolean(), nullable=False),
        sa.Column("repeat_measurement_reason", sa.String(1000)),
        sa.Column("note", sa.String(2000)),
        sa.Column("occurred_at", TZ, nullable=False),
        sa.Column("recorded_at", TZ, nullable=False),
        sa.Column("correlation_id", UUID_TYPE, nullable=False),
        sa.Column(
            "supersedes_review_id",
            UUID_TYPE,
            sa.ForeignKey("clinician_troponin_reviews.review_id", ondelete="RESTRICT"),
        ),
        sa.Column("record_version", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_clinician_troponin_reviews_case", "clinician_troponin_reviews", ["clinical_case_id"]
    )
    op.create_table(
        "repeat_troponin_requests",
        sa.Column("request_id", UUID_TYPE, primary_key=True),
        sa.Column(
            "clinical_case_id",
            UUID_TYPE,
            sa.ForeignKey("clinical_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_result_id",
            UUID_TYPE,
            sa.ForeignKey("troponin_evidence_results.result_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "requested_by_actor_id",
            UUID_TYPE,
            sa.ForeignKey("clinical_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("requested_at", TZ, nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column(
            "acknowledged_by_actor_id",
            UUID_TYPE,
            sa.ForeignKey("clinical_users.id", ondelete="RESTRICT"),
        ),
        sa.Column("acknowledged_at", TZ),
        sa.Column(
            "completed_result_id",
            UUID_TYPE,
            sa.ForeignKey("troponin_evidence_results.result_id", ondelete="RESTRICT"),
        ),
        sa.Column("completed_at", TZ),
        sa.Column("cancellation_reason", sa.String(1000)),
        sa.Column("correlation_id", UUID_TYPE, nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_repeat_trop_case_status", "repeat_troponin_requests", ["clinical_case_id", "status"]
    )
    assays = sa.table(
        "troponin_assay_definitions",
        sa.column("assay_id", UUID_TYPE),
        sa.column("code"),
        sa.column("display_name"),
        sa.column("analyte"),
        sa.column("category"),
        sa.column("manufacturer"),
        sa.column("platform"),
        sa.column("assay_version"),
        sa.column("canonical_unit"),
        sa.column("effective_version"),
        sa.column("active"),
    )
    op.bulk_insert(
        assays,
        [
            {
                "assay_id": UUID("b4010000-0000-4000-8000-000000000001"),
                "code": "DEMO-HS-CTNI-01",
                "display_name": "Demonstration high-sensitivity cardiac troponin I",
                "analyte": "cardiac_troponin_i",
                "category": "hs_ctni",
                "manufacturer": "Synthetic demonstration catalog",
                "platform": "Mock laboratory platform",
                "assay_version": "demo-1",
                "canonical_unit": "ng/L",
                "effective_version": 1,
                "active": True,
            },
            {
                "assay_id": UUID("b4010000-0000-4000-8000-000000000002"),
                "code": "DEMO-HS-CTNT-01",
                "display_name": "Demonstration high-sensitivity cardiac troponin T",
                "analyte": "cardiac_troponin_t",
                "category": "hs_ctnt",
                "manufacturer": "Synthetic demonstration catalog",
                "platform": "Mock laboratory platform",
                "assay_version": "demo-1",
                "canonical_unit": "ng/L",
                "effective_version": 1,
                "active": True,
            },
            {
                "assay_id": UUID("b4010000-0000-4000-8000-000000000003"),
                "code": "UNKNOWN-TROPONIN",
                "display_name": "Unknown troponin assay",
                "analyte": "unknown_troponin",
                "category": "unknown",
                "manufacturer": "Unknown",
                "platform": "Unknown",
                "assay_version": "unknown-1",
                "canonical_unit": None,
                "effective_version": 1,
                "active": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_repeat_trop_case_status", table_name="repeat_troponin_requests")
    op.drop_table("repeat_troponin_requests")
    op.drop_index("ix_clinician_troponin_reviews_case", table_name="clinician_troponin_reviews")
    op.drop_table("clinician_troponin_reviews")
    op.drop_index("ix_lab_import_external", table_name="laboratory_import_jobs")
    op.drop_index("ix_lab_import_case", table_name="laboratory_import_jobs")
    op.drop_index("ix_lab_import_status", table_name="laboratory_import_jobs")
    op.drop_table("laboratory_import_jobs")
    op.drop_index("ix_trop_result_status", table_name="troponin_evidence_results")
    op.drop_index("ix_trop_result_assay", table_name="troponin_evidence_results")
    op.drop_index("ix_trop_accession", table_name="troponin_evidence_results")
    op.drop_index("ix_trop_case_specimen", table_name="troponin_evidence_results")
    op.drop_table("troponin_evidence_results")
    op.drop_index("ix_troponin_assay_definitions_code", table_name="troponin_assay_definitions")
    op.drop_table("troponin_assay_definitions")
