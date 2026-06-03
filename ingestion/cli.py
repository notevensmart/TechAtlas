import argparse
from dataclasses import replace
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _import(args: argparse.Namespace) -> None:
    from app.db.session import SessionLocal
    from app.services.importer import import_file

    path = Path(args.path)
    rejects_path = Path(args.rejects) if args.rejects else None
    with SessionLocal() as session:
        result = import_file(session, path=path, rejects_path=rejects_path)
    print(
        "Import completed: "
        f"run_id={result.import_run_id} "
        f"seen={result.rows_seen} "
        f"imported={result.rows_imported} "
        f"rejected={result.rows_rejected}"
    )
    if result.rejects_path:
        print(f"Rejected rows written to {result.rejects_path}")


def _sync_jobdata(args: argparse.Namespace) -> None:
    from app.db.session import SessionLocal
    from app.services.importer import import_rows
    from app.services.jobdataapi import fetch_jobdata_rows

    queries = args.query or None
    raw_output = Path(args.raw_output) if args.raw_output else None
    rejects_path = Path(args.rejects) if args.rejects else None
    sync = fetch_jobdata_rows(
        days=args.days,
        page_size=args.page_size,
        max_pages_per_query=args.max_pages,
        queries=queries,
        raw_output_path=raw_output,
    )

    with SessionLocal() as session:
        result = import_rows(
            session,
            sync.canonical_rows,
            file_name=f"jobdataapi:{args.days}d",
            rejects_path=rejects_path,
        )

    print(
        "JobDataAPI sync completed: "
        f"raw_seen={sync.raw_seen} "
        f"canonical={len(sync.canonical_rows)} "
        f"run_id={result.import_run_id} "
        f"imported={result.rows_imported} "
        f"rejected={result.rows_rejected}"
    )
    if sync.raw_output_path:
        print(f"Raw API response JSONL written to {sync.raw_output_path}")
    if result.rejects_path:
        print(f"Rejected rows written to {result.rejects_path}")


def _crawl_structured(args: argparse.Namespace) -> None:
    import json

    from app.db.session import SessionLocal
    from app.services.crawler import CrawlConfig, StructuredJobCrawler, read_seed_urls
    from app.services.importer import import_rows

    seed_urls = read_seed_urls(args.seeds)
    crawler = StructuredJobCrawler(
        CrawlConfig(
            request_delay_seconds=args.delay,
            max_urls=args.max_urls,
            discover_depth=args.discover_depth,
            timeout_seconds=args.timeout,
            user_agent=args.user_agent,
            obey_robots=True,
            verify_tls=not args.insecure_skip_tls_verify,
        )
    )
    result = crawler.crawl(seed_urls)

    canonical_output = Path(args.canonical_output) if args.canonical_output else None
    if canonical_output:
        canonical_output.parent.mkdir(parents=True, exist_ok=True)
        with canonical_output.open("w", encoding="utf-8") as handle:
            for row in result.extracted_rows:
                handle.write(json.dumps(row, ensure_ascii=True))
                handle.write("\n")

    print(
        "Crawler completed: "
        f"seeds={len(seed_urls)} "
        f"fetched={result.fetched_pages} "
        f"skipped={len(result.skipped_urls)} "
        f"extracted={len(result.extracted_rows)}"
    )

    if not result.extracted_rows:
        print("No structured JobPosting records were found; nothing imported.")
        return

    rejects_path = Path(args.rejects) if args.rejects else None
    with SessionLocal() as session:
        import_result = import_rows(
            session,
            result.extracted_rows,
            file_name=f"crawler:{Path(args.seeds).name}",
            rejects_path=rejects_path,
        )

    print(
        "Crawler import completed: "
        f"run_id={import_result.import_run_id} "
        f"imported={import_result.rows_imported} "
        f"rejected={import_result.rows_rejected}"
    )
    if canonical_output:
        print(f"Canonical crawler rows written to {canonical_output}")
    if import_result.rejects_path:
        print(f"Rejected rows written to {import_result.rejects_path}")


def _crawl_all(args: argparse.Namespace) -> None:
    import json

    from app.db.session import SessionLocal
    from app.services.crawler import CrawlConfig
    from app.services.importer import import_rows
    from app.services.source_crawler import (
        SourceCrawler,
        create_crawl_run,
        finish_crawl_run,
        persist_raw_records,
    )
    from app.services.source_registry import DEFAULT_SOURCES_PATH, load_source_registry

    registry_path = Path(args.sources) if args.sources else DEFAULT_SOURCES_PATH
    selected_keys = set(args.source or [])
    sources = load_source_registry(registry_path)
    if selected_keys:
        sources = [source for source in sources if source.key in selected_keys]
        missing = selected_keys - {source.key for source in sources}
        if missing:
            raise SystemExit(f"unknown source key(s): {', '.join(sorted(missing))}")
    elif not args.include_disabled:
        sources = [source for source in sources if source.enabled]

    if args.max_urls is not None or args.discover_depth is not None:
        sources = [
            replace(
                source,
                max_urls=args.max_urls if args.max_urls is not None else source.max_urls,
                discover_depth=args.discover_depth if args.discover_depth is not None else source.discover_depth,
            )
            for source in sources
        ]

    crawler = SourceCrawler(
        CrawlConfig(
            request_delay_seconds=args.delay,
            max_urls=args.max_urls or 100,
            timeout_seconds=args.timeout,
            user_agent=args.user_agent,
            obey_robots=True,
            verify_tls=not args.insecure_skip_tls_verify,
        )
    )

    canonical_rows: list[dict[str, object]] = []
    for source in sources:
        print(f"Crawling {source.key} via {source.adapter}...")
        with SessionLocal() as session:
            run = create_crawl_run(session, source)

        try:
            result = crawler.crawl_source(source)
            rows = [record.canonical_row for record in result.records]
            canonical_rows.extend(rows)
            with SessionLocal() as session:
                persist_raw_records(session, run.id, result)

            imported = 0
            if rows:
                rejects_path = None
                if args.rejects_dir:
                    rejects_dir = Path(args.rejects_dir)
                    rejects_dir.mkdir(parents=True, exist_ok=True)
                    rejects_path = rejects_dir / f"{source.key.replace(':', '_')}_rejects.csv"
                with SessionLocal() as session:
                    import_result = import_rows(
                        session,
                        rows,
                        file_name=f"crawl-all:{source.key}",
                        rejects_path=rejects_path,
                    )
                imported = import_result.rows_imported

            with SessionLocal() as session:
                finish_crawl_run(
                    session,
                    run.id,
                    status="completed",
                    result=result,
                    rows_imported=imported,
                )

            print(
                f"  fetched={result.pages_fetched} "
                f"skipped={result.pages_skipped} "
                f"extracted={len(result.records)} "
                f"imported={imported}"
            )
        except Exception as exc:
            with SessionLocal() as session:
                finish_crawl_run(session, run.id, status="failed", error_message=str(exc))
            print(f"  failed: {exc}")

    if args.canonical_output:
        output_path = Path(args.canonical_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            for row in canonical_rows:
                handle.write(json.dumps(row, ensure_ascii=True))
                handle.write("\n")
        print(f"Canonical crawler rows written to {output_path}")

    print(f"Crawl-all completed: sources={len(sources)} extracted={len(canonical_rows)}")


def _scheduled_crawl(args: argparse.Namespace) -> None:
    import json

    from app.services.scheduled_crawl import run_scheduled_crawl

    def print_progress(event: dict[str, object]) -> None:
        print(json.dumps(event, ensure_ascii=True, sort_keys=True), flush=True)

    try:
        result = run_scheduled_crawl(
            registry_path=Path(args.sources) if args.sources else None,
            selected_source_keys=args.source or None,
            profile_name=args.profile,
            max_urls=args.max_urls,
            delay=args.delay,
            timeout=args.timeout,
            source_timeout=args.source_timeout,
            canonical_output_path=Path(args.canonical_output) if args.canonical_output else None,
            rejects_dir=Path(args.rejects_dir) if args.rejects_dir else None,
            insecure_skip_tls_verify=args.insecure_skip_tls_verify,
            user_agent=args.user_agent,
            expire_after_days=args.expire_after_days,
            expire_after_successful_crawls=args.expire_after_successful_crawls,
            expire_partial_sources=args.expire_partial_sources,
            abandon_running_after_minutes=args.abandon_running_after_minutes,
            dry_run=args.dry_run,
            progress=None if args.dry_run else print_progress,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "command": "scheduled-crawl",
                    "status": "failed",
                    "error_message": str(exc),
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        raise SystemExit(2) from exc

    print(result.to_json())


def _source_report(args: argparse.Namespace) -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import CrawlRun

    with SessionLocal() as session:
        runs = session.scalars(
            select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(args.limit)
        ).all()

    if not runs:
        print("No crawl runs recorded yet.")
        return

    for run in runs:
        finished = run.finished_at.isoformat() if run.finished_at else ""
        print(
            f"#{run.id} {run.source_key} {run.status} "
            f"fetched={run.pages_fetched} skipped={run.pages_skipped} "
            f"extracted={run.rows_extracted} imported={run.rows_imported} "
            f"finished={finished}"
        )


def _scout_sources(args: argparse.Namespace) -> None:
    import yaml

    from app.services.crawler import CrawlConfig, read_seed_urls
    from app.services.source_crawler import SourceScout, discovered_sources_to_registry

    seed_urls = read_seed_urls(args.seeds)
    scout = SourceScout(
        CrawlConfig(
            request_delay_seconds=args.delay,
            max_urls=args.max_urls,
            timeout_seconds=args.timeout,
            user_agent=args.user_agent,
            obey_robots=True,
            verify_tls=not args.insecure_skip_tls_verify,
        )
    )
    discovered = scout.scout(seed_urls)
    registry = discovered_sources_to_registry(discovered)
    rendered = yaml.safe_dump(registry, sort_keys=False, allow_unicode=False)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        print(f"Discovered source registry written to {output_path}")
    else:
        print(rendered)
    print(f"Scout completed: seeds={len(seed_urls)} discovered={len(discovered)}")


def _seed_skills(_: argparse.Namespace) -> None:
    from app.db.session import SessionLocal
    from app.services.taxonomy import seed_skills

    with SessionLocal() as session:
        changed = seed_skills(session)
        session.commit()
    print(f"Skill taxonomy seeded. Changed rows: {changed}")


def _refresh(_: argparse.Namespace) -> None:
    from app.db.session import SessionLocal
    from app.services.aggregates import refresh_daily_skill_snapshots

    with SessionLocal() as session:
        rows = refresh_daily_skill_snapshots(session)
        session.commit()
    print(f"Daily skill snapshots refreshed. Rows written: {rows}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="techatlas-ingest")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import", help="Import permitted CSV/JSONL job data")
    import_parser.add_argument("path", help="Path to .csv, .jsonl, or .ndjson file")
    import_parser.add_argument("--rejects", help="Optional path for rejected-row CSV report")
    import_parser.set_defaults(func=_import)

    jobdata_parser = subparsers.add_parser("sync-jobdata", help="Sync recent Australian jobs from JobDataAPI")
    jobdata_parser.add_argument("--days", type=int, default=30, help="Recent age window in days")
    jobdata_parser.add_argument("--page-size", type=int, default=200, help="JobDataAPI page size")
    jobdata_parser.add_argument("--max-pages", type=int, default=3, help="Maximum pages per role query")
    jobdata_parser.add_argument(
        "--query",
        action="append",
        help="Role title query to sync. Repeat to provide multiple queries. Defaults to TechAtlas role taxonomy.",
    )
    jobdata_parser.add_argument("--raw-output", help="Optional JSONL path for raw API jobs")
    jobdata_parser.add_argument("--rejects", help="Optional path for rejected-row CSV report")
    jobdata_parser.set_defaults(func=_sync_jobdata)

    crawler_parser = subparsers.add_parser(
        "crawl-structured",
        help="Crawl permitted URLs and extract schema.org JobPosting JSON-LD",
    )
    crawler_parser.add_argument("seeds", help="Text file containing one permitted seed URL per line")
    crawler_parser.add_argument("--max-urls", type=int, default=100, help="Maximum pages to fetch")
    crawler_parser.add_argument(
        "--discover-depth",
        type=int,
        default=0,
        help="Same-host job/career link discovery depth. 0 fetches only seed URLs.",
    )
    crawler_parser.add_argument("--delay", type=float, default=1.5, help="Per-host delay between requests")
    crawler_parser.add_argument("--timeout", type=float, default=20, help="HTTP request timeout in seconds")
    crawler_parser.add_argument(
        "--user-agent",
        default="TechAtlasBot/0.1 (+local portfolio project)",
        help="Crawler User-Agent sent to target sites",
    )
    crawler_parser.add_argument(
        "--insecure-skip-tls-verify",
        action="store_true",
        help="Disable TLS certificate verification for local debugging only",
    )
    crawler_parser.add_argument("--canonical-output", help="Optional JSONL path for canonical extracted rows")
    crawler_parser.add_argument("--rejects", help="Optional path for rejected-row CSV report")
    crawler_parser.set_defaults(func=_crawl_structured)

    crawl_all_parser = subparsers.add_parser(
        "crawl-all",
        help="Run configured HTML source adapters from ingestion/sources.yml",
    )
    crawl_all_parser.add_argument("--sources", help="Path to source registry YAML")
    crawl_all_parser.add_argument(
        "--source",
        action="append",
        help="Source key to crawl. Repeat for multiple keys. Defaults to all enabled sources.",
    )
    crawl_all_parser.add_argument("--include-disabled", action="store_true", help="Include disabled sources")
    crawl_all_parser.add_argument("--max-urls", type=int, help="Override max pages per source")
    crawl_all_parser.add_argument("--discover-depth", type=int, help="Override link discovery depth")
    crawl_all_parser.add_argument("--delay", type=float, default=1.5, help="Per-host delay between requests")
    crawl_all_parser.add_argument("--timeout", type=float, default=20, help="HTTP request timeout in seconds")
    crawl_all_parser.add_argument(
        "--user-agent",
        default="TechAtlasBot/0.1 (+local portfolio project)",
        help="Crawler User-Agent sent to target sites",
    )
    crawl_all_parser.add_argument(
        "--insecure-skip-tls-verify",
        action="store_true",
        help="Disable TLS certificate verification for local debugging only",
    )
    crawl_all_parser.add_argument("--canonical-output", help="Optional JSONL path for canonical extracted rows")
    crawl_all_parser.add_argument("--rejects-dir", help="Optional directory for per-source reject CSV reports")
    crawl_all_parser.set_defaults(func=_crawl_all)

    scheduled_parser = subparsers.add_parser(
        "scheduled-crawl",
        help="Run enabled configured sources with automation-safe profiles, import, freshness, and expiry",
    )
    scheduled_parser.add_argument("--sources", help="Path to source registry YAML")
    scheduled_parser.add_argument(
        "--source",
        action="append",
        help="Source key to crawl. Repeat for multiple keys. Defaults to all enabled sources.",
    )
    scheduled_parser.add_argument(
        "--profile",
        choices=["conservative", "normal", "heavy"],
        default="conservative",
        help="Crawl profile. Defaults to conservative for unattended runs.",
    )
    scheduled_parser.add_argument("--max-urls", type=int, help="Override profile/source max pages per source")
    scheduled_parser.add_argument("--delay", type=float, help="Override profile per-host delay between requests")
    scheduled_parser.add_argument("--timeout", type=float, help="Override profile HTTP request timeout in seconds")
    scheduled_parser.add_argument("--source-timeout", type=float, help="Override wall-clock timeout per source in seconds")
    scheduled_parser.add_argument(
        "--user-agent",
        default="TechAtlasBot/0.1 (+local portfolio project)",
        help="Crawler User-Agent sent to target sites",
    )
    scheduled_parser.add_argument(
        "--canonical-output",
        help="Optional JSONL path for canonical extracted rows",
    )
    scheduled_parser.add_argument(
        "--rejects-dir",
        help="Optional directory for per-source reject CSV reports",
    )
    scheduled_parser.add_argument(
        "--expire-after-days",
        type=int,
        default=45,
        help="Expire unobserved listings after this many days since last_seen_at",
    )
    scheduled_parser.add_argument(
        "--expire-after-successful-crawls",
        type=int,
        default=3,
        help="Expire unobserved listings after this many successful source crawls since last_seen_at",
    )
    scheduled_parser.add_argument(
        "--expire-partial-sources",
        action="store_true",
        help="Allow expiry for partial or low-confidence adapters such as search-result card sources",
    )
    scheduled_parser.add_argument(
        "--abandon-running-after-minutes",
        type=int,
        default=180,
        help="Mark unfinished running crawl rows older than this many minutes as abandoned before starting",
    )
    scheduled_parser.add_argument(
        "--insecure-skip-tls-verify",
        action="store_true",
        help="Disable TLS certificate verification for local debugging only",
    )
    scheduled_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve sources and profile without fetching, importing, or expiring listings",
    )
    scheduled_parser.set_defaults(func=_scheduled_crawl)

    report_parser = subparsers.add_parser("source-report", help="Show recent configured crawler runs")
    report_parser.add_argument("--limit", type=int, default=20)
    report_parser.set_defaults(func=_source_report)

    scout_parser = subparsers.add_parser(
        "scout-sources",
        help="Discover supported ATS sources from public careers pages",
    )
    scout_parser.add_argument("seeds", help="Text file containing careers/source URLs to inspect")
    scout_parser.add_argument("--output", help="Optional YAML path for discovered source registry entries")
    scout_parser.add_argument("--max-urls", type=int, default=50, help="Maximum pages to inspect")
    scout_parser.add_argument("--delay", type=float, default=1.5, help="Per-host delay between requests")
    scout_parser.add_argument("--timeout", type=float, default=20, help="HTTP request timeout in seconds")
    scout_parser.add_argument(
        "--user-agent",
        default="TechAtlasBot/0.1 (+local portfolio project)",
        help="Crawler User-Agent sent to target sites",
    )
    scout_parser.add_argument(
        "--insecure-skip-tls-verify",
        action="store_true",
        help="Disable TLS certificate verification for local debugging only",
    )
    scout_parser.set_defaults(func=_scout_sources)

    seed_parser = subparsers.add_parser("seed-skills", help="Seed the YAML skill taxonomy into Postgres")
    seed_parser.set_defaults(func=_seed_skills)

    refresh_parser = subparsers.add_parser("refresh-aggregates", help="Rebuild aggregate skill snapshots")
    refresh_parser.set_defaults(func=_refresh)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
