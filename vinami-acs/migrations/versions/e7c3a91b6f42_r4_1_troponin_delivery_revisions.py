"""Add source-delivery revisions for the R4.1 deterministic laboratory lifecycle.

Revision ID: e7c3a91b6f42
Revises: d6b8f2a4c901
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7c3a91b6f42"
down_revision: str | None = "d6b8f2a4c901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "troponin_evidence_results",
        sa.Column("source_identity", sa.String(length=400), nullable=True),
    )
    op.add_column(
        "troponin_evidence_results",
        sa.Column("source_revision", sa.Integer(), nullable=True),
    )
    op.execute(
        "UPDATE troponin_evidence_results "
        "SET source_identity = source_result_id, source_revision = 1 "
        "WHERE source_identity IS NULL OR source_revision IS NULL"
    )
    op.alter_column("troponin_evidence_results", "source_identity", nullable=False)
    op.alter_column("troponin_evidence_results", "source_revision", nullable=False)
    op.drop_constraint("uq_trop_source_result", "troponin_evidence_results", type_="unique")
    op.create_unique_constraint(
        "uq_trop_source_revision",
        "troponin_evidence_results",
        ["source_system", "source_identity", "source_revision"],
    )
    op.add_column(
        "clinician_troponin_reviews",
        sa.Column("correction_reason", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("clinician_troponin_reviews", "correction_reason")
    op.drop_constraint("uq_trop_source_revision", "troponin_evidence_results", type_="unique")
    op.create_unique_constraint(
        "uq_trop_source_result",
        "troponin_evidence_results",
        ["source_system", "source_result_id"],
    )
    op.drop_column("troponin_evidence_results", "source_revision")
    op.drop_column("troponin_evidence_results", "source_identity")
