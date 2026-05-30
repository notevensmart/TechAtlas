# Crawler Logic

TechAtlas includes an owned acquisition layer for permitted public careers sources. It is designed around local source adapters, a source registry, raw record retention, and transparent AU-tech filtering.

It does not depend on paid job APIs. It does not bypass robots rules, does not use browser automation, and is not wired to crawl SEEK.

## What It Does

- Reads configured sources from `ingestion/sources.yml`.
- Checks `robots.txt` before fetching each URL.
- Applies a per-host request delay.
- Fetches HTML pages only.
- Runs a source adapter:
  - `lever-html` discovers Lever board links and extracts direct posting data.
  - `greenhouse-html` parses Greenhouse board/detail HTML state.
  - `ashby-html` parses Ashby board/detail HTML state.
  - `generic-jsonld` extracts `schema.org/JobPosting` JSON-LD.
- Filters to Australian tech roles using local rule-based intelligence.
- Stores raw extracted records in `raw_job_records`.
- Records crawler health in `crawl_runs`.
- Maps postings into the existing TechAtlas canonical import rows.
- Imports extracted rows through the same validation and analytics refresh path as CSV/JSONL.

## Source Registry

`ingestion/sources.yml` is the source of truth for crawler inputs:

```yaml
sources:
  - key: greenhouse:roller
    adapter: greenhouse-html
    enabled: true
    seeds:
      - https://job-boards.greenhouse.io/roller
    discover_depth: 1
    max_urls: 80
    filters:
      country: AU
      tech_only: true
```

Each source declares its adapter, seed pages, crawl limit, filters, and compliance note.

## Command

Run all enabled sources:

```bash
python -m ingestion.cli crawl-all --canonical-output data/crawl_all_rows.jsonl --rejects-dir data/rejects
```

Run one source:

```bash
python -m ingestion.cli crawl-all --source greenhouse:roller --max-urls 40
```

Show recent runs:

```bash
python -m ingestion.cli source-report
```

Scout ordinary careers pages for supported ATS boards:

```bash
python -m ingestion.cli scout-sources careers_seed_urls.txt --output data/discovered_sources.yml
```

The scout reads public HTML links and emits registry entries for supported sources such as Lever, Greenhouse, Ashby, and direct pages that expose `schema.org/JobPosting`.

## Safety Defaults

- `robots.txt` is always obeyed.
- Default per-host delay is 1.5 seconds.
- TLS certificate verification is enabled by default.
- Only `http` and `https` URLs are accepted.
- Non-HTML responses are skipped.
- Sources outside the registry are not crawled by `crawl-all`.
- Non-AU or non-tech roles are filtered before import.

If a local development machine has broken CA certificates, you can test with:

```bash
python -m ingestion.cli crawl-all --insecure-skip-tls-verify
```

Use that flag only for local debugging.

## Ad Hoc Structured Crawl

For experiments, `crawl-structured` still accepts a plain seed file and extracts generic `schema.org/JobPosting` JSON-LD:

```bash
python -m ingestion.cli crawl-structured seeds.txt --max-urls 25 --canonical-output data/crawler_rows.jsonl
```

## Limitations

This crawler intentionally targets public careers pages and HTML-exposed job state. Many job boards load data through private APIs or JavaScript-rendered applications; those sources should get dedicated adapters only when permission and terms are clear.
