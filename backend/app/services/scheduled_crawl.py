from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.services.crawler import CrawlConfig
from app.services.freshness import (
    DEFAULT_EXPIRE_AFTER_DAYS,
    DEFAULT_EXPIRE_AFTER_SUCCESSFUL_CRAWLS,
    ExpiryResult,
    expire_missing_listings,
)
from app.services.importer import ImportResult, import_rows
from app.services.source_crawler import (
    SourceCrawler,
    SourceCrawlResult,
    create_crawl_run,
    finish_crawl_run,
    persist_raw_records,
)
from app.services.source_registry import DEFAULT_SOURCES_PATH, SourceDefinition, load_source_registry


DEFAULT_USER_AGENT = "TechAtlasBot/0.1 (+local portfolio project)"


@dataclass(frozen=True)
class CrawlProfile:
    name: str
    max_urls: int
    delay_seconds: float
    timeout_seconds: float


CRAWL_PROFILES: dict[str, CrawlProfile] = {
    "conservative": CrawlProfile(
        name="conservative",
        max_urls=25,
        delay_seconds=3.0,
        timeout_seconds=20.0,
    ),
    "normal": CrawlProfile(
        name="normal",
        max_urls=100,
        delay_seconds=1.5,
        timeout_seconds=20.0,
    ),
    "heavy": CrawlProfile(
        name="heavy",
        max_urls=300,
        delay_seconds=2.0,
        timeout_seconds=30.0,
    ),
}


@dataclass
class SourceScheduledResult:
    source_key: str
    adapter: str
    status: str
    crawl_run_id: int | None = None
    import_run_id: int | None = None
    pages_fetched: int = 0
    pages_skipped: int = 0
    rows_extracted: int = 0
    rows_imported: int = 0
    rows_rejected: int = 0
    raw_records_persisted: int = 0
    expired_listings: int = 0
    expiry_checked_listings: int = 0
    expiry_skipped_reason: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_key,
            "adapter": self.adapter,
            "status": self.status,
            "crawl_run_id": self.crawl_run_id,
            "import_run_id": self.import_run_id,
            "pages_fetched": self.pages_fetched,
            "pages_skipped": self.pages_skipped,
            "rows_extracted": self.rows_extracted,
            "rows_imported": self.rows_imported,
            "rows_rejected": self.rows_rejected,
            "raw_records_persisted": self.raw_records_persisted,
            "expiry_checked_listings": self.expiry_checked_listings,
            "expired_listings": self.expired_listings,
            "expiry_skipped_reason": self.expiry_skipped_reason,
            "error_message": self.error_message,
        }


@dataclass
class ScheduledCrawlResult:
    profile: CrawlProfile
    started_at: datetime
    finished_at: datetime
    sources: list[SourceScheduledResult]
    canonical_output_path: Path | None = None
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        completed = sum(1 for item in self.sources if item.status == "completed")
        failed = sum(1 for item in self.sources if item.status == "failed")
        planned = sum(1 for item in self.sources if item.status == "planned")
        return {
            "command": "scheduled-crawl",
            "profile": self.profile.name,
            "dry_run": self.dry_run,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "sources_total": len(self.sources),
            "sources_completed": completed,
            "sources_failed": failed,
            "sources_planned": planned,
            "pages_fetched": sum(item.pages_fetched for item in self.sources),
            "pages_skipped": sum(item.pages_skipped for item in self.sources),
            "rows_extracted": sum(item.rows_extracted for item in self.sources),
            "rows_imported": sum(item.rows_imported for item in self.sources),
            "rows_rejected": sum(item.rows_rejected for item in self.sources),
            "expired_listings": sum(item.expired_listings for item in self.sources),
            "canonical_output": str(self.canonical_output_path) if self.canonical_output_path else None,
            "sources": [item.to_dict() for item in self.sources],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=True, sort_keys=True)


def resolve_crawl_profile(
    profile_name: str,
    *,
    max_urls: int | None = None,
    delay: float | None = None,
    timeout: float | None = None,
) -> CrawlProfile:
    profile = CRAWL_PROFILES.get(profile_name)
    if profile is None:
        raise ValueError(f"unknown crawl profile: {profile_name}")
    return CrawlProfile(
        name=profile.name,
        max_urls=max_urls if max_urls is not None else profile.max_urls,
        delay_seconds=delay if delay is not None else profile.delay_seconds,
        timeout_seconds=timeout if timeout is not None else profile.timeout_seconds,
    )


def select_sources(
    registry_path: Path | None = None,
    *,
    selected_source_keys: list[str] | None = None,
) -> list[SourceDefinition]:
    sources = load_source_registry(registry_path or DEFAULT_SOURCES_PATH)
    selected = set(selected_source_keys or [])
    if selected:
        matched = [source for source in sources if source.key in selected]
        missing = selected - {source.key for source in matched}
        if missing:
            raise ValueError(f"unknown source key(s): {', '.join(sorted(missing))}")
        return matched
    return [source for source in sources if source.enabled]


def apply_profile_to_source(
    source: SourceDefinition,
    profile: CrawlProfile,
    *,
    max_urls_override: bool = False,
) -> SourceDefinition:
    if max_urls_override:
        return replace(source, max_urls=profile.max_urls)

    source_max_urls = source.max_urls if source.max_urls is not None else profile.max_urls
    if profile.name == "conservative":
        max_urls = min(source_max_urls, profile.max_urls)
    elif profile.name == "heavy":
        max_urls = max(source_max_urls, profile.max_urls)
    else:
        max_urls = source_max_urls
    return replace(source, max_urls=max_urls)


def _default_session_factory():
    from app.db.session import SessionLocal

    return SessionLocal


def _rejects_path(rejects_dir: Path | None, source_key: str) -> Path | None:
    if rejects_dir is None:
        return None
    rejects_dir.mkdir(parents=True, exist_ok=True)
    return rejects_dir / f"{source_key.replace(':', '_')}_rejects.csv"


def _import_rows(
    session: Session,
    rows: list[dict[str, object]],
    *,
    source_key: str,
    rejects_dir: Path | None,
) -> ImportResult:
    return import_rows(
        session,
        rows,
        file_name=f"scheduled-crawl:{source_key}",
        rejects_path=_rejects_path(rejects_dir, source_key),
    )


def _apply_expiry(
    session: Session,
    *,
    source: SourceDefinition,
    result: SourceCrawlResult,
    expire_after_days: int,
    expire_after_successful_crawls: int,
    allow_partial_sources: bool,
) -> ExpiryResult:
    return expire_missing_listings(
        session,
        source=source,
        observed_external_ids={record.external_id for record in result.records},
        expire_after_days=expire_after_days,
        expire_after_successful_crawls=expire_after_successful_crawls,
        allow_partial_sources=allow_partial_sources,
    )


def run_scheduled_crawl(
    *,
    registry_path: Path | None = None,
    selected_source_keys: list[str] | None = None,
    profile_name: str = "conservative",
    max_urls: int | None = None,
    delay: float | None = None,
    timeout: float | None = None,
    canonical_output_path: Path | None = None,
    rejects_dir: Path | None = None,
    insecure_skip_tls_verify: bool = False,
    user_agent: str = DEFAULT_USER_AGENT,
    expire_after_days: int = DEFAULT_EXPIRE_AFTER_DAYS,
    expire_after_successful_crawls: int = DEFAULT_EXPIRE_AFTER_SUCCESSFUL_CRAWLS,
    expire_partial_sources: bool = False,
    dry_run: bool = False,
    session_factory: Callable[[], Any] | None = None,
    crawler_factory: Callable[[CrawlConfig], SourceCrawler] = SourceCrawler,
) -> ScheduledCrawlResult:
    started_at = datetime.now(timezone.utc)
    profile = resolve_crawl_profile(profile_name, max_urls=max_urls, delay=delay, timeout=timeout)
    selected_sources = select_sources(registry_path, selected_source_keys=selected_source_keys)
    sources = [
        apply_profile_to_source(source, profile, max_urls_override=max_urls is not None)
        for source in selected_sources
    ]

    if not sources:
        raise ValueError("no enabled sources selected for scheduled crawl")

    if dry_run:
        planned = [
            SourceScheduledResult(source_key=source.key, adapter=source.adapter, status="planned")
            for source in sources
        ]
        return ScheduledCrawlResult(
            profile=profile,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            sources=planned,
            dry_run=True,
        )

    session_factory = session_factory or _default_session_factory()
    crawler = crawler_factory(
        CrawlConfig(
            request_delay_seconds=profile.delay_seconds,
            max_urls=profile.max_urls,
            timeout_seconds=profile.timeout_seconds,
            user_agent=user_agent,
            obey_robots=True,
            verify_tls=not insecure_skip_tls_verify,
        )
    )

    canonical_rows: list[dict[str, object]] = []
    source_results: list[SourceScheduledResult] = []
    for source in sources:
        with session_factory() as session:
            run = create_crawl_run(session, source)

        source_result = SourceScheduledResult(
            source_key=source.key,
            adapter=source.adapter,
            status="running",
            crawl_run_id=run.id,
        )
        try:
            crawl_result = crawler.crawl_source(source)
            rows = [record.canonical_row for record in crawl_result.records]
            canonical_rows.extend(rows)
            source_result.pages_fetched = crawl_result.pages_fetched
            source_result.pages_skipped = crawl_result.pages_skipped
            source_result.rows_extracted = len(crawl_result.records)

            with session_factory() as session:
                source_result.raw_records_persisted = persist_raw_records(session, run.id, crawl_result)

            if rows:
                with session_factory() as session:
                    import_result = _import_rows(
                        session,
                        rows,
                        source_key=source.key,
                        rejects_dir=rejects_dir,
                    )
                source_result.import_run_id = import_result.import_run_id
                source_result.rows_imported = import_result.rows_imported
                source_result.rows_rejected = import_result.rows_rejected

            with session_factory() as session:
                finish_crawl_run(
                    session,
                    run.id,
                    status="completed",
                    result=crawl_result,
                    rows_imported=source_result.rows_imported,
                )

            with session_factory() as session:
                expiry = _apply_expiry(
                    session,
                    source=source,
                    result=crawl_result,
                    expire_after_days=expire_after_days,
                    expire_after_successful_crawls=expire_after_successful_crawls,
                    allow_partial_sources=expire_partial_sources,
                )
                session.commit()
            source_result.expiry_checked_listings = expiry.checked_listings
            source_result.expired_listings = expiry.expired_listings
            source_result.expiry_skipped_reason = expiry.skipped_reason
            source_result.status = "completed"
        except Exception as exc:
            source_result.status = "failed"
            source_result.error_message = str(exc)
            with session_factory() as session:
                finish_crawl_run(session, run.id, status="failed", error_message=str(exc))
        source_results.append(source_result)

    if canonical_output_path:
        canonical_output_path.parent.mkdir(parents=True, exist_ok=True)
        with canonical_output_path.open("w", encoding="utf-8") as handle:
            for row in canonical_rows:
                handle.write(json.dumps(row, ensure_ascii=True))
                handle.write("\n")

    return ScheduledCrawlResult(
        profile=profile,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        sources=source_results,
        canonical_output_path=canonical_output_path,
    )
