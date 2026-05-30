"""crawler acquisition layer

Revision ID: 0002_crawler_acquisition_layer
Revises: 0001_initial
Create Date: 2026-05-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_crawler_acquisition_layer"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("listings", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("listings", sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("listings", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_listings_last_seen_at", "listings", ["last_seen_at"], unique=False)

    op.create_table(
        "crawl_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=120), nullable=False),
        sa.Column("adapter", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seed_count", sa.Integer(), nullable=False),
        sa.Column("pages_fetched", sa.Integer(), nullable=False),
        sa.Column("pages_skipped", sa.Integer(), nullable=False),
        sa.Column("rows_extracted", sa.Integer(), nullable=False),
        sa.Column("rows_imported", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crawl_runs_source_key", "crawl_runs", ["source_key"], unique=False)
    op.create_index("ix_crawl_runs_started_at", "crawl_runs", ["started_at"], unique=False)

    op.create_table(
        "raw_job_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("crawl_run_id", sa.Integer(), nullable=True),
        sa.Column("source_key", sa.String(length=120), nullable=False),
        sa.Column("adapter", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("canonical_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["crawl_run_id"], ["crawl_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_raw_job_records_content_hash", "raw_job_records", ["content_hash"], unique=False)
    op.create_index("ix_raw_job_records_observed_at", "raw_job_records", ["observed_at"], unique=False)
    op.create_index("ix_raw_job_records_source_key", "raw_job_records", ["source_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_raw_job_records_source_key", table_name="raw_job_records")
    op.drop_index("ix_raw_job_records_observed_at", table_name="raw_job_records")
    op.drop_index("ix_raw_job_records_content_hash", table_name="raw_job_records")
    op.drop_table("raw_job_records")
    op.drop_index("ix_crawl_runs_started_at", table_name="crawl_runs")
    op.drop_index("ix_crawl_runs_source_key", table_name="crawl_runs")
    op.drop_table("crawl_runs")
    op.drop_index("ix_listings_last_seen_at", table_name="listings")
    op.drop_column("listings", "content_hash")
    op.drop_column("listings", "expired_at")
    op.drop_column("listings", "last_seen_at")
    op.drop_column("listings", "first_seen_at")
