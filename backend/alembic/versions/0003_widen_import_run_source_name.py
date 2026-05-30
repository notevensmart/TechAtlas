"""widen import run source name

Revision ID: 0003_widen_import_source
Revises: 0002_crawler_acquisition_layer
Create Date: 2026-05-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_widen_import_source"
down_revision: str | None = "0002_crawler_acquisition_layer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "import_runs",
        "source_name",
        existing_type=sa.String(length=80),
        type_=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "import_runs",
        "source_name",
        existing_type=sa.String(length=255),
        type_=sa.String(length=80),
        existing_nullable=True,
    )
