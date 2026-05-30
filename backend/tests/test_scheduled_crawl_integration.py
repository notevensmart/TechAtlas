import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

if not os.getenv("TEST_DATABASE_URL"):
    pytest.skip(
        "requires TEST_DATABASE_URL pointing at a disposable PostgreSQL database",
        allow_module_level=True,
    )

from app.db.base import Base  # noqa: E402
from app.models import DailySkillSnapshot, Listing, Source  # noqa: E402
from app.services.importer import import_rows  # noqa: E402
from app.services.scheduled_crawl import run_scheduled_crawl  # noqa: E402
from app.services.source_crawler import ExtractedJobRecord, SourceCrawlResult  # noqa: E402


@pytest.fixture()
def session_factory():
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _registry(tmp_path: Path, *, adapter: str = "lever-html") -> Path:
    path = tmp_path / "sources.yml"
    path.write_text(
        f"""
sources:
  - key: lever:example
    adapter: {adapter}
    enabled: true
    seeds:
      - https://jobs.lever.co/example
    max_urls: 5
    filters:
      country: AU
      tech_only: true
""",
        encoding="utf-8",
    )
    return path


def _row(
    *,
    external_id: str,
    observed_at: datetime,
    content_hash: str,
    title: str = "Backend Engineer",
) -> dict[str, object]:
    return {
        "source": "lever:example",
        "external_id": external_id,
        "title": title,
        "company": "Example",
        "location": "Sydney NSW",
        "description": "Build Python services on AWS with PostgreSQL.",
        "listed_at": "2026-05-01T00:00:00Z",
        "source_url": f"https://jobs.lever.co/example/{external_id}",
        "observed_at": observed_at.isoformat(),
        "content_hash": content_hash,
        "role_hint": title,
    }


def _record(source, *, external_id: str, observed_at: datetime, content_hash: str, title: str = "Backend Engineer"):
    row = _row(
        external_id=external_id,
        observed_at=observed_at,
        content_hash=content_hash,
        title=title,
    )
    return ExtractedJobRecord(
        source_key=source.key,
        adapter=source.adapter,
        source_url=str(row["source_url"]),
        external_id=external_id,
        observed_at=observed_at,
        content_hash=content_hash,
        raw_payload={"title": title},
        canonical_row=row,
    )


def _crawler_factory(records_by_external_id=None, *, fail: bool = False):
    records_by_external_id = records_by_external_id or {}

    class FakeCrawler:
        def __init__(self, config):
            self.config = config

        def crawl_source(self, source):
            if fail:
                raise RuntimeError("simulated source failure")
            return SourceCrawlResult(
                source=source,
                visited_urls=["https://jobs.lever.co/example"],
                skipped_urls=[],
                records=[
                    _record(source, external_id=external_id, **record_args)
                    for external_id, record_args in records_by_external_id.items()
                ],
            )

    return FakeCrawler


def _listing(session, external_id: str) -> Listing:
    return session.scalar(
        select(Listing).join(Source, Source.id == Listing.source_id).where(
            Source.name == "lever:example",
            Listing.external_id == external_id,
        )
    )


def test_successful_scheduled_crawl_updates_last_seen_at(tmp_path: Path, session_factory) -> None:
    registry = _registry(tmp_path)
    old_seen = datetime.now(timezone.utc) - timedelta(days=60)
    new_seen = datetime.now(timezone.utc)

    with session_factory() as session:
        import_rows(session, [_row(external_id="job-1", observed_at=old_seen, content_hash="hash-old")], file_name="seed")

    result = run_scheduled_crawl(
        registry_path=registry,
        selected_source_keys=["lever:example"],
        profile_name="normal",
        session_factory=session_factory,
        crawler_factory=_crawler_factory(
            {
                "job-1": {
                    "observed_at": new_seen,
                    "content_hash": "hash-new",
                    "title": "Senior Backend Engineer",
                }
            }
        ),
    )

    assert result.to_dict()["sources_completed"] == 1
    with session_factory() as session:
        listing = _listing(session, "job-1")
        assert listing is not None
        assert listing.first_seen_at == old_seen
        assert listing.last_seen_at == new_seen
        assert listing.title == "Senior Backend Engineer"
        assert listing.content_hash == "hash-new"
        assert listing.expired_at is None


def test_missing_listings_are_not_expired_on_failed_crawl(tmp_path: Path, session_factory) -> None:
    registry = _registry(tmp_path)
    old_seen = datetime.now(timezone.utc) - timedelta(days=60)

    with session_factory() as session:
        import_rows(session, [_row(external_id="job-1", observed_at=old_seen, content_hash="hash-old")], file_name="seed")

    result = run_scheduled_crawl(
        registry_path=registry,
        selected_source_keys=["lever:example"],
        profile_name="normal",
        session_factory=session_factory,
        crawler_factory=_crawler_factory(fail=True),
        expire_after_days=1,
    )

    assert result.to_dict()["sources_failed"] == 1
    with session_factory() as session:
        listing = _listing(session, "job-1")
        assert listing.expired_at is None


def test_missing_listings_expire_after_threshold_on_successful_crawl(tmp_path: Path, session_factory) -> None:
    registry = _registry(tmp_path)
    old_seen = datetime.now(timezone.utc) - timedelta(days=60)
    new_seen = datetime.now(timezone.utc)

    with session_factory() as session:
        import_rows(
            session,
            [
                _row(external_id="job-1", observed_at=old_seen, content_hash="hash-1-old"),
                _row(external_id="job-2", observed_at=old_seen, content_hash="hash-2-old"),
            ],
            file_name="seed",
        )

    result = run_scheduled_crawl(
        registry_path=registry,
        selected_source_keys=["lever:example"],
        profile_name="normal",
        session_factory=session_factory,
        crawler_factory=_crawler_factory(
            {"job-1": {"observed_at": new_seen, "content_hash": "hash-1-new"}}
        ),
        expire_after_days=45,
    )

    assert result.to_dict()["expired_listings"] == 1
    with session_factory() as session:
        observed = _listing(session, "job-1")
        missing = _listing(session, "job-2")
        assert observed.expired_at is None
        assert missing.expired_at is not None


def test_aggregates_refresh_after_successful_scheduled_import(tmp_path: Path, session_factory) -> None:
    registry = _registry(tmp_path)
    observed_at = datetime.now(timezone.utc)

    result = run_scheduled_crawl(
        registry_path=registry,
        selected_source_keys=["lever:example"],
        profile_name="normal",
        session_factory=session_factory,
        crawler_factory=_crawler_factory(
            {"job-1": {"observed_at": observed_at, "content_hash": "hash-new"}}
        ),
    )

    assert result.to_dict()["rows_imported"] == 1
    with session_factory() as session:
        snapshot_count = session.scalar(select(DailySkillSnapshot).limit(1))
        assert snapshot_count is not None
