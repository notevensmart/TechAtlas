"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=80), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_seen", sa.Integer(), nullable=False),
        sa.Column("rows_imported", sa.Integer(), nullable=False),
        sa.Column("rows_rejected", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_import_runs_source_name"), "import_runs", ["source_name"], unique=False)

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sources_name"), "sources", ["name"], unique=True)

    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("patterns", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("case_sensitive", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_skills_name"), "skills", ["name"], unique=True)
    op.create_index("ix_skills_category", "skills", ["category"], unique=False)

    op.create_table(
        "listings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("raw_location", sa.Text(), nullable=False),
        sa.Column("city", sa.String(length=64), nullable=False),
        sa.Column("description_raw", sa.Text(), nullable=False),
        sa.Column("listed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_period", sa.String(length=24), nullable=True),
        sa.Column("salary_min_annual", sa.Integer(), nullable=True),
        sa.Column("salary_max_annual", sa.Integer(), nullable=True),
        sa.Column("salary_mid_annual", sa.Integer(), nullable=True),
        sa.Column("work_mode", sa.String(length=32), nullable=False),
        sa.Column("work_type", sa.String(length=64), nullable=True),
        sa.Column("experience_level", sa.String(length=32), nullable=False),
        sa.Column("role_family", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "external_id", name="uq_listing_source_external"),
    )
    op.create_index("ix_listings_city", "listings", ["city"], unique=False)
    op.create_index("ix_listings_experience_level", "listings", ["experience_level"], unique=False)
    op.create_index("ix_listings_listed_at", "listings", ["listed_at"], unique=False)
    op.create_index("ix_listings_role_family", "listings", ["role_family"], unique=False)
    op.create_index("ix_listings_work_mode", "listings", ["work_mode"], unique=False)

    op.create_table(
        "daily_skill_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("city", sa.String(length=64), nullable=True),
        sa.Column("role_family", sa.String(length=64), nullable=True),
        sa.Column("experience_level", sa.String(length=32), nullable=True),
        sa.Column("work_mode", sa.String(length=32), nullable=True),
        sa.Column("listing_count", sa.Integer(), nullable=False),
        sa.Column("total_postings", sa.Integer(), nullable=False),
        sa.Column("share_of_postings_pct", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_daily_skill_snapshots_date_skill",
        "daily_skill_snapshots",
        ["snapshot_date", "skill_id"],
        unique=False,
    )
    op.create_index(
        "ix_daily_skill_snapshots_dimensions",
        "daily_skill_snapshots",
        ["city", "role_family", "experience_level", "work_mode"],
        unique=False,
    )

    op.create_table(
        "listing_query_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("query", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "query", name="uq_listing_query_match"),
    )
    op.create_index("ix_listing_query_matches_query", "listing_query_matches", ["query"], unique=False)

    op.create_table(
        "listing_skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "skill_id", name="uq_listing_skill"),
    )
    op.create_index("ix_listing_skills_listing_id", "listing_skills", ["listing_id"], unique=False)
    op.create_index("ix_listing_skills_skill_id", "listing_skills", ["skill_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_listing_skills_skill_id", table_name="listing_skills")
    op.drop_index("ix_listing_skills_listing_id", table_name="listing_skills")
    op.drop_table("listing_skills")
    op.drop_index("ix_listing_query_matches_query", table_name="listing_query_matches")
    op.drop_table("listing_query_matches")
    op.drop_index("ix_daily_skill_snapshots_dimensions", table_name="daily_skill_snapshots")
    op.drop_index("ix_daily_skill_snapshots_date_skill", table_name="daily_skill_snapshots")
    op.drop_table("daily_skill_snapshots")
    op.drop_index("ix_listings_work_mode", table_name="listings")
    op.drop_index("ix_listings_role_family", table_name="listings")
    op.drop_index("ix_listings_listed_at", table_name="listings")
    op.drop_index("ix_listings_experience_level", table_name="listings")
    op.drop_index("ix_listings_city", table_name="listings")
    op.drop_table("listings")
    op.drop_index("ix_skills_category", table_name="skills")
    op.drop_index(op.f("ix_skills_name"), table_name="skills")
    op.drop_table("skills")
    op.drop_index(op.f("ix_sources_name"), table_name="sources")
    op.drop_table("sources")
    op.drop_index(op.f("ix_import_runs_source_name"), table_name="import_runs")
    op.drop_table("import_runs")

