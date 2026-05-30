from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    listings: Mapped[list["Listing"]] = relationship(back_populates="source")


class CrawlRun(Base):
    __tablename__ = "crawl_runs"
    __table_args__ = (
        Index("ix_crawl_runs_source_key", "source_key"),
        Index("ix_crawl_runs_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(120), nullable=False)
    adapter: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    seed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_extracted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    raw_records: Mapped[list["RawJobRecord"]] = relationship(
        back_populates="crawl_run", cascade="all, delete-orphan"
    )


class RawJobRecord(Base):
    __tablename__ = "raw_job_records"
    __table_args__ = (
        Index("ix_raw_job_records_source_key", "source_key"),
        Index("ix_raw_job_records_observed_at", "observed_at"),
        Index("ix_raw_job_records_content_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    crawl_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("crawl_runs.id", ondelete="CASCADE"), nullable=True
    )
    source_key: Mapped[str] = mapped_column(String(120), nullable=False)
    adapter: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    canonical_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    crawl_run: Mapped[CrawlRun | None] = relationship(back_populates="raw_records")


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rows_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_listing_source_external"),
        Index("ix_listings_listed_at", "listed_at"),
        Index("ix_listings_last_seen_at", "last_seen_at"),
        Index("ix_listings_city", "city"),
        Index("ix_listings_role_family", "role_family"),
        Index("ix_listings_experience_level", "experience_level"),
        Index("ix_listings_work_mode", "work_mode"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str] = mapped_column(Text, nullable=False)
    raw_location: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(String(64), nullable=False, default="Other")
    description_raw: Mapped[str] = mapped_column(Text, nullable=False)
    listed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_period: Mapped[str | None] = mapped_column(String(24), nullable=True)
    salary_min_annual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max_annual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_mid_annual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    work_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    experience_level: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    role_family: Mapped[str] = mapped_column(String(64), nullable=False, default="Other/Unknown")

    source: Mapped[Source] = relationship(back_populates="listings")
    query_matches: Mapped[list["ListingQueryMatch"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )
    skill_links: Mapped[list["ListingSkill"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )


class ListingQueryMatch(Base):
    __tablename__ = "listing_query_matches"
    __table_args__ = (
        UniqueConstraint("listing_id", "query", name="uq_listing_query_match"),
        Index("ix_listing_query_matches_query", "query"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    query: Mapped[str] = mapped_column(String(120), nullable=False)

    listing: Mapped[Listing] = relationship(back_populates="query_matches")


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (Index("ix_skills_category", "category"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    patterns: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    case_sensitive: Mapped[bool] = mapped_column(default=False, nullable=False)

    listing_links: Mapped[list["ListingSkill"]] = relationship(back_populates="skill")


class ListingSkill(Base):
    __tablename__ = "listing_skills"
    __table_args__ = (
        UniqueConstraint("listing_id", "skill_id", name="uq_listing_skill"),
        Index("ix_listing_skills_listing_id", "listing_id"),
        Index("ix_listing_skills_skill_id", "skill_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"))

    listing: Mapped[Listing] = relationship(back_populates="skill_links")
    skill: Mapped[Skill] = relationship(back_populates="listing_links")


class DailySkillSnapshot(Base):
    __tablename__ = "daily_skill_snapshots"
    __table_args__ = (
        Index("ix_daily_skill_snapshots_date_skill", "snapshot_date", "skill_id"),
        Index("ix_daily_skill_snapshots_dimensions", "city", "role_family", "experience_level", "work_mode"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role_family: Mapped[str | None] = mapped_column(String(64), nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    work_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    listing_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_postings: Mapped[int] = mapped_column(Integer, nullable=False)
    share_of_postings_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)
