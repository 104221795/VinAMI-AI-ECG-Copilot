"""Align R10 integration message indexes with ORM metadata.

Revision ID: f3b6c8d1e245
Revises: e2a1b7c9d010
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f3b6c8d1e245"
down_revision: str | None = "e2a1b7c9d010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_integration_clinical_case_id", table_name="integration_messages")
    op.drop_index("ix_integration_message_type", table_name="integration_messages")
    op.create_index(
        "ix_integration_messages_clinical_case_id",
        "integration_messages",
        ["clinical_case_id"],
    )
    op.create_index(
        "ix_integration_messages_message_type",
        "integration_messages",
        ["message_type"],
    )
    op.create_index(
        "ix_integration_messages_received_at",
        "integration_messages",
        ["received_at"],
    )
    op.create_index(
        "ix_integration_messages_status",
        "integration_messages",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_integration_messages_status", table_name="integration_messages")
    op.drop_index("ix_integration_messages_received_at", table_name="integration_messages")
    op.drop_index("ix_integration_messages_message_type", table_name="integration_messages")
    op.drop_index("ix_integration_messages_clinical_case_id", table_name="integration_messages")
    op.create_index(
        "ix_integration_message_type",
        "integration_messages",
        ["message_type"],
    )
    op.create_index(
        "ix_integration_clinical_case_id",
        "integration_messages",
        ["clinical_case_id"],
    )
