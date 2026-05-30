from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CrawlRun, Listing, Source
from app.services.source_registry import SourceDefinition


PARTIAL_OR_LOW_CONFIDENCE_ADAPTERS = {"careerone-search"}
DEFAULT_EXPIRE_AFTER_DAYS = 45
DEFAULT_EXPIRE_AFTER_SUCCESSFUL_CRAWLS = 3


@dataclass(frozen=True)
class ExpiryResult:
    source_key: str
    checked_listings: int
    expired_listings: int
    skipped_reason: str | None = None


def _reference_seen_at(listing: Listing) -> datetime:
    return listing.last_seen_at or listing.first_seen_at or listing.imported_at or listing.listed_at


def expire_missing_listings(
    session: Session,
    *,
    source: SourceDefinition,
    observed_external_ids: set[str],
    expire_after_days: int = DEFAULT_EXPIRE_AFTER_DAYS,
    expire_after_successful_crawls: int = DEFAULT_EXPIRE_AFTER_SUCCESSFUL_CRAWLS,
    allow_partial_sources: bool = False,
    now: datetime | None = None,
) -> ExpiryResult:
    """Mark listings expired only after a successful, sufficiently fresh source observation.

    The scheduler calls this after a source crawl and import have completed. It never
    deletes rows; it only sets expired_at for unexpired listings that were absent
    from the latest source observation and have aged past conservative thresholds.
    """

    if source.adapter in PARTIAL_OR_LOW_CONFIDENCE_ADAPTERS and not allow_partial_sources:
        return ExpiryResult(
            source_key=source.key,
            checked_listings=0,
            expired_listings=0,
            skipped_reason="partial_or_low_confidence_source",
        )

    source_row = session.scalar(select(Source).where(Source.name == source.key))
    if source_row is None:
        return ExpiryResult(
            source_key=source.key,
            checked_listings=0,
            expired_listings=0,
            skipped_reason="source_not_imported",
        )

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(expire_after_days, 0))
    query = select(Listing).where(
        Listing.source_id == source_row.id,
        Listing.expired_at.is_(None),
    )
    if observed_external_ids:
        query = query.where(Listing.external_id.not_in(observed_external_ids))

    candidates = session.scalars(query).all()
    expired = 0
    for listing in candidates:
        seen_at = _reference_seen_at(listing)
        older_than_threshold = seen_at <= cutoff
        missed_successful_crawls = 0
        if expire_after_successful_crawls > 0:
            missed_successful_crawls = (
                session.scalar(
                    select(func.count(CrawlRun.id)).where(
                        CrawlRun.source_key == source.key,
                        CrawlRun.status == "completed",
                        CrawlRun.finished_at.is_not(None),
                        CrawlRun.finished_at > seen_at,
                    )
                )
                or 0
            )

        if older_than_threshold or missed_successful_crawls >= expire_after_successful_crawls:
            listing.expired_at = now
            expired += 1

    session.flush()
    return ExpiryResult(
        source_key=source.key,
        checked_listings=len(candidates),
        expired_listings=expired,
    )
