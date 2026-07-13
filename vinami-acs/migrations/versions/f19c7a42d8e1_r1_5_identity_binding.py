"""R1.5 verified identity binding and audit provenance.

Revision ID: f19c7a42d8e1
Revises: d4c8a91e7b32
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f19c7a42d8e1"
down_revision = "d4c8a91e7b32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add known roles, stable provider-subject bindings, and safe audit identity fields."""
    for enum_value in (
        "TECHNICIAN",
        "CARE_COORDINATOR",
        "ADMINISTRATOR",
        "AUDITOR",
        "SYSTEM_SERVICE",
        "READ_ONLY_REVIEWER",
    ):
        op.execute(f"ALTER TYPE clinical_role ADD VALUE IF NOT EXISTS '{enum_value}'")

    op.add_column("clinical_users", sa.Column("identity_subject", sa.String(255), nullable=True))
    op.add_column("clinical_users", sa.Column("identity_provider", sa.String(500), nullable=True))
    op.add_column(
        "clinical_users", sa.Column("authentication_method", sa.String(80), nullable=True)
    )
    op.add_column("clinical_users", sa.Column("organization", sa.String(200), nullable=True))
    op.add_column(
        "clinical_users",
        sa.Column(
            "location_scope",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("clinical_users", "location_scope", server_default=None)
    op.create_unique_constraint(
        "uq_clinical_user_provider_subject",
        "clinical_users",
        ["identity_provider", "identity_subject"],
    )

    op.add_column("audit_logs", sa.Column("identity_subject", sa.String(255), nullable=True))
    op.add_column(
        "audit_logs",
        sa.Column(
            "actor_roles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("audit_logs", "actor_roles", server_default=None)
    op.add_column("audit_logs", sa.Column("applied_permission", sa.String(120), nullable=True))
    op.add_column("audit_logs", sa.Column("identity_provider", sa.String(500), nullable=True))
    op.add_column(
        "audit_logs", sa.Column("authentication_method", sa.String(80), nullable=True)
    )
    op.add_column("audit_logs", sa.Column("session_reference", sa.String(255), nullable=True))
    op.create_index("ix_audit_logs_identity_subject", "audit_logs", ["identity_subject"])
    op.create_index("ix_audit_logs_outcome", "audit_logs", ["outcome"])


def downgrade() -> None:
    """Remove R1.5 binding columns; PostgreSQL enum values remain harmlessly available."""
    op.drop_index("ix_audit_logs_outcome", table_name="audit_logs")
    op.drop_index("ix_audit_logs_identity_subject", table_name="audit_logs")
    for column in (
        "session_reference",
        "authentication_method",
        "identity_provider",
        "applied_permission",
        "actor_roles",
        "identity_subject",
    ):
        op.drop_column("audit_logs", column)
    op.drop_constraint(
        "uq_clinical_user_provider_subject", "clinical_users", type_="unique"
    )
    for column in (
        "location_scope",
        "organization",
        "authentication_method",
        "identity_provider",
        "identity_subject",
    ):
        op.drop_column("clinical_users", column)
