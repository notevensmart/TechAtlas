from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import CrawlRun
from app.services.freshness import ExpiryResult
from app.services.importer import ImportResult
from app.services.scheduled_crawl import (
    abandon_stale_crawl_runs,
    apply_profile_to_source,
    resolve_crawl_profile,
    run_scheduled_crawl,
)
from app.services.source_crawler import ExtractedJobRecord, SourceCrawlResult
from app.services.source_registry import SourceDefinition


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self) -> None:
        return None


def _registry(path: Path) -> None:
    path.write_text(
        """
sources:
  - key: lever:bad
    adapter: lever-html
    enabled: true
    seeds:
      - https://jobs.lever.co/bad
  - key: lever:ok
    adapter: lever-html
    enabled: true
    seeds:
      - https://jobs.lever.co/ok
""",
        encoding="utf-8",
    )


def test_scheduled_crawl_profile_resolution() -> None:
    source = SourceDefinition(
        key="lever:example",
        adapter="lever-html",
        seeds=["https://jobs.lever.co/example"],
        max_urls=120,
    )

    conservative = resolve_crawl_profile("conservative")
    normal = resolve_crawl_profile("normal")
    heavy = resolve_crawl_profile("heavy")
    override = resolve_crawl_profile("conservative", max_urls=7, delay=4.5, timeout=9, source_timeout=60)

    assert apply_profile_to_source(source, conservative).max_urls == 25
    assert apply_profile_to_source(source, normal).max_urls == 120
    assert apply_profile_to_source(source, heavy).max_urls == 300
    assert conservative.max_source_runtime_seconds == 600
    assert apply_profile_to_source(source, override, max_urls_override=True).max_urls == 7
    assert override.max_urls == 7
    assert override.delay_seconds == 4.5
    assert override.timeout_seconds == 9
    assert override.max_source_runtime_seconds == 60


def test_stale_running_crawl_runs_are_marked_abandoned() -> None:
    engine = create_engine("sqlite:///:memory:")
    CrawlRun.__table__.create(engine)
    now = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        session.add_all(
            [
                CrawlRun(
                    source_key="lever:palantir",
                    adapter="lever-html",
                    status="running",
                    seed_count=1,
                    started_at=now - timedelta(hours=4),
                ),
                CrawlRun(
                    source_key="lever:recent",
                    adapter="lever-html",
                    status="running",
                    seed_count=1,
                    started_at=now - timedelta(minutes=20),
                ),
                CrawlRun(
                    source_key="lever:done",
                    adapter="lever-html",
                    status="completed",
                    seed_count=1,
                    started_at=now - timedelta(hours=6),
                    finished_at=now - timedelta(hours=5),
                ),
            ]
        )
        session.commit()

        abandoned = abandon_stale_crawl_runs(
            session,
            stale_before=now - timedelta(minutes=180),
            abandon_after_minutes=180,
            now=now,
        )
        runs = {run.source_key: run for run in session.scalars(select(CrawlRun)).all()}

    assert abandoned == 1
    assert runs["lever:palantir"].status == "abandoned"
    assert runs["lever:palantir"].finished_at == now.replace(tzinfo=None)
    assert "180 minutes" in runs["lever:palantir"].error_message
    assert runs["lever:recent"].status == "running"
    assert runs["lever:done"].status == "completed"


def test_one_failed_source_does_not_abort_all_sources(monkeypatch, tmp_path: Path) -> None:
    registry = tmp_path / "sources.yml"
    _registry(registry)
    finished: list[tuple[int, str]] = []

    class FakeCrawler:
        def __init__(self, config):
            self.config = config

        def crawl_source(self, source):
            if source.key == "lever:bad":
                raise RuntimeError("source failed")
            observed_at = datetime(2026, 5, 30, tzinfo=timezone.utc)
            record = ExtractedJobRecord(
                source_key=source.key,
                adapter=source.adapter,
                source_url="https://jobs.lever.co/ok/job-1",
                external_id="job-1",
                observed_at=observed_at,
                content_hash="hash-1",
                raw_payload={"title": "Backend Engineer"},
                canonical_row={
                    "source": source.key,
                    "external_id": "job-1",
                    "title": "Backend Engineer",
                    "company": "Example",
                    "location": "Sydney NSW",
                    "description": "Build Python services on AWS.",
                    "listed_at": "2026-05-01T00:00:00Z",
                    "source_url": "https://jobs.lever.co/ok/job-1",
                    "observed_at": observed_at.isoformat(),
                    "content_hash": "hash-1",
                },
            )
            return SourceCrawlResult(
                source=source,
                visited_urls=["https://jobs.lever.co/ok"],
                skipped_urls=[],
                records=[record],
            )

    def fake_create_crawl_run(session, source):
        return SimpleNamespace(id=1 if source.key == "lever:bad" else 2)

    def fake_finish_crawl_run(session, crawl_run_id, *, status, **kwargs):
        finished.append((crawl_run_id, status))

    def fake_import_rows(session, rows, *, file_name, rejects_path=None, csv_columns=None):
        return ImportResult(
            rows_seen=len(rows),
            rows_imported=len(rows),
            rows_rejected=0,
            import_run_id=42,
            rejects_path=None,
        )

    monkeypatch.setattr("app.services.scheduled_crawl.create_crawl_run", fake_create_crawl_run)
    monkeypatch.setattr("app.services.scheduled_crawl.finish_crawl_run", fake_finish_crawl_run)
    monkeypatch.setattr("app.services.scheduled_crawl.abandon_stale_crawl_runs", lambda *args, **kwargs: 0)
    monkeypatch.setattr("app.services.scheduled_crawl.persist_raw_records", lambda session, run_id, result: len(result.records))
    monkeypatch.setattr("app.services.scheduled_crawl.import_rows", fake_import_rows)
    monkeypatch.setattr(
        "app.services.scheduled_crawl._apply_expiry",
        lambda *args, **kwargs: ExpiryResult("lever:ok", checked_listings=0, expired_listings=0),
    )

    result = run_scheduled_crawl(
        registry_path=registry,
        profile_name="normal",
        session_factory=FakeSession,
        crawler_factory=FakeCrawler,
    )

    summary = result.to_dict()
    assert summary["sources_total"] == 2
    assert summary["sources_completed"] == 1
    assert summary["sources_failed"] == 1
    assert summary["rows_imported"] == 1
    assert (1, "failed") in finished
    assert (2, "completed") in finished
