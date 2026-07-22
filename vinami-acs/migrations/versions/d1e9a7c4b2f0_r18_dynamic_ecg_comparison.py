"""Add R18 structured dynamic ECG comparison evidence.

Revision ID: d1e9a7c4b2f0
Revises: f3b6c8d1e245
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from vinami.shared.persistence import JSONDocument

revision: str = "d1e9a7c4b2f0"
down_revision: str | None = "f3b6c8d1e245"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dynamic_ecg_comparisons",
        sa.Column(
            "signal_feature_deltas",
            JSONDocument,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "dynamic_ecg_comparisons",
        sa.Column(
            "rhythm_change_indicators",
            JSONDocument,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "dynamic_ecg_comparisons",
        sa.Column(
            "st_t_change_indicators",
            JSONDocument,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "dynamic_ecg_comparisons",
        sa.Column(
            "review_recommendation",
            sa.Text(),
            nullable=False,
            server_default=(
                "Technical serial ECG comparison only; "
                "physician interpretation is required."
            ),
        ),
    )


def downgrade() -> None:
    for column in (
        "review_recommendation",
        "st_t_change_indicators",
        "rhythm_change_indicators",
        "signal_feature_deltas",
    ):
        op.drop_column("dynamic_ecg_comparisons", column)
