"""Add R10 real-time and hospital integration message ledger.

Revision ID: e2a1b7c9d010
Revises: c1f7a5e9d204
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from vinami.shared.persistence import JSONDocument

revision: str = "e2a1b7c9d010"
down_revision: str | None = "c1f7a5e9d204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_messages",
        sa.Column("message_id", sa.Uuid(), primary_key=True),
        sa.Column("external_message_id", sa.String(240), nullable=False),
        sa.Column("source_system", sa.String(160), nullable=False),
        sa.Column("message_type", sa.String(80), nullable=False),
        sa.Column("schema_version", sa.String(120), nullable=False),
        sa.Column("clinical_case_id", sa.Uuid(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("causation_id", sa.Uuid(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("validation_errors", JSONDocument, nullable=False),
        sa.Column("linked_record_ids", JSONDocument, nullable=False),
        sa.Column("payload", JSONDocument, nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("dead_letter_reason", sa.Text(), nullable=True),
        sa.Column("simulated", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("record_version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "source_system", "external_message_id", name="uq_integration_source_msg"
        ),
    )
    op.create_index("ix_integration_message_type", "integration_messages", ["message_type"])
    op.create_index("ix_integration_clinical_case_id", "integration_messages", ["clinical_case_id"])
    op.create_index(
        "ix_integration_status_received", "integration_messages", ["status", "received_at"]
    )
    op.create_index(
        "ix_integration_case_received",
        "integration_messages",
        ["clinical_case_id", "received_at"],
    )
    op.create_index("ix_integration_correlation", "integration_messages", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_integration_correlation", table_name="integration_messages")
    op.drop_index("ix_integration_case_received", table_name="integration_messages")
    op.drop_index("ix_integration_status_received", table_name="integration_messages")
    op.drop_index("ix_integration_clinical_case_id", table_name="integration_messages")
    op.drop_index("ix_integration_message_type", table_name="integration_messages")
    op.drop_table("integration_messages")
