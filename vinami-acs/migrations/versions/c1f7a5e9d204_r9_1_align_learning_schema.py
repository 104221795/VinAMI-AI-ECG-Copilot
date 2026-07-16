"""Align R9 learning export schema with ORM metadata.

Revision ID: c1f7a5e9d204
Revises: b4e2d9c7a103
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c1f7a5e9d204"
down_revision: str | None = "b4e2d9c7a103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in ("case_ids", "filters", "content_json", "metadata"):
        op.execute(
            "ALTER TABLE clinical_research_exports "
            f"ALTER COLUMN {column} TYPE jsonb USING {column}::jsonb"
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_outcomes_causation_id ON outcomes (causation_id)"
    )


def downgrade() -> None:
    for column in ("case_ids", "filters", "content_json", "metadata"):
        op.execute(
            "ALTER TABLE clinical_research_exports "
            f"ALTER COLUMN {column} TYPE json USING {column}::json"
        )
