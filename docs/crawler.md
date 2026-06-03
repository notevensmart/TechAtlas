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

Run the automation-friendly scheduled loop:

```bash
python -m ingestion.cli scheduled-crawl --profile conservative --canonical-output data/scheduled_crawl_rows.jsonl --rejects-dir data/rejects
```

Run selected sources:

```bash
python -m ingestion.cli scheduled-crawl --source greenhouse:roller --source lever:upguard --profile normal
```

The command prints one compact JSON summary as its final line. Individual source failures are reported in that summary but do not make the process exit non-zero; registry, argument, or database-wide failures still exit non-zero.

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

## Scheduled Crawl Profiles

`scheduled-crawl` reads `ingestion/sources.yml` and defaults to enabled sources only. Repeating `--source` selects explicit registry keys.

Profiles:

- `conservative`: caps each source at 25 URLs, uses a 3.0 second per-host delay, caps each source at 600 seconds, and is the default for unattended jobs.
- `normal`: keeps current practical source limits where configured, with a 1.5 second per-host delay and a 1800 second source runtime cap.
- `heavy`: raises source limits to at least 300 URLs, with a 2.0 second per-host delay, a longer request timeout, and a 5400 second source runtime cap.

Overrides:

```bash
python -m ingestion.cli scheduled-crawl --profile conservative --max-urls 10 --delay 5 --timeout 15
```

Profiles and overrides never disable `robots.txt`; the scheduler always constructs the crawler with `obey_robots=True`.

Use `--source-timeout` to override the wall-clock runtime cap for each source. When a source exceeds its cap, that source is marked failed and later sources continue. Scheduled crawls also emit JSON progress lines as sources start, complete, or fail, so cron logs show where a run stopped.

If a previous process was killed mid-source, its `crawl_runs` row can remain `running`. By default, scheduled startup marks unfinished runs older than 180 minutes as `abandoned`; override this with `--abandon-running-after-minutes`.

## Freshness And Expiry

Imports still upsert listings by `source + external_id`. Re-observed listings keep their original `first_seen_at`, update `last_seen_at` to the crawl observation time, update `content_hash` and listing fields when content changes, and clear `expired_at` because the listing has been seen again.

Date semantics:

- `listed_at`: the market listing date from the source.
- `imported_at`: TechAtlas import/update time.
- `first_seen_at`: first TechAtlas observation.
- `last_seen_at`: most recent TechAtlas observation.
- `expired_at`: when TechAtlas decides a listing is no longer observed.

Missing listings are never hard-deleted. After a successful source crawl and import, TechAtlas compares the current extracted external IDs with unexpired listings for that source. A missing listing is marked expired only after it is older than `--expire-after-days` or has missed `--expire-after-successful-crawls` completed source runs.

Default:

```bash
python -m ingestion.cli scheduled-crawl --expire-after-days 45 --expire-after-successful-crawls 3
```

The scheduler does not expire listings when a source crawl fails. Partial or low-confidence adapters such as `careerone-search` are not expired by default; use `--expire-partial-sources` only when you have reviewed that source and accepted the risk.

## Scheduler Examples

Windows Task Scheduler, from PowerShell:

```powershell
$repo = "C:\Users\parth\OneDrive\Documents\ML projects\techjob_market_analysis\TechAtlas"
$python = "$repo\.venv\Scripts\python.exe"
$args = "-m ingestion.cli scheduled-crawl --profile conservative --canonical-output data\scheduled_crawl_latest.jsonl --rejects-dir data\rejects"
$action = New-ScheduledTaskAction -Execute $python -Argument $args -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Daily -At 6:30am
Register-ScheduledTask -TaskName "TechAtlas scheduled crawl" -Action $action -Trigger $trigger -Description "Conservative TechAtlas source refresh"
```

Cron:

```cron
30 20 * * * cd /srv/TechAtlas && /srv/TechAtlas/.venv/bin/python -m ingestion.cli scheduled-crawl --profile conservative --canonical-output data/scheduled_crawl_latest.jsonl --rejects-dir data/rejects >> logs/scheduled-crawl.log 2>&1
```

Railway scheduled job:

Railway cron jobs run a service start command on a crontab schedule and expect the process to exit when the task is done. Use a separate Railway service/job for the crawler, point it at the same repo and database, and set the start command to:

```bash
python -m ingestion.cli scheduled-crawl --profile conservative
```

Set the Railway cron schedule in UTC, for example `30 20 * * *` for a daily off-peak run. Keep the API service start command as `uvicorn ...`; the crawler should be a separate short-lived cron service. Railway skips a scheduled run if the previous execution is still running, so keep profiles conservative unless you have measured runtime. See the current [Railway cron reference](https://docs.railway.com/reference/cron-jobs).

Scout ordinary careers pages for supported ATS boards:

```bash
python -m ingestion.cli scout-sources careers_seed_urls.txt --output data/discovered_sources.yml
```

The scout reads public HTML links and emits registry entries for supported sources such as Lever, Greenhouse, Ashby, and direct pages that expose `schema.org/JobPosting`.

## Safety Defaults

- `robots.txt` is always obeyed.
- Scheduled runs default to the conservative profile.
- Per-host delay is preserved for every profile.
- TLS certificate verification is enabled by default.
- Only `http` and `https` URLs are accepted.
- Non-HTML responses are skipped.
- Sources outside the registry are not crawled by `crawl-all`.
- Only enabled registry sources are scheduled by default.
- Non-AU or non-tech roles are filtered before import.
- Missing listings are marked stale/expired only after successful source crawls and conservative thresholds.

If a local development machine has broken CA certificates, you can test with:

```bash
python -m ingestion.cli scheduled-crawl --source greenhouse:roller --insecure-skip-tls-verify
```

Use that flag only for local debugging.

## Ad Hoc Structured Crawl

For experiments, `crawl-structured` still accepts a plain seed file and extracts generic `schema.org/JobPosting` JSON-LD:

```bash
python -m ingestion.cli crawl-structured seeds.txt --max-urls 25 --canonical-output data/crawler_rows.jsonl
```

## Limitations

This crawler intentionally targets public careers pages and HTML-exposed job state. Many job boards load data through private APIs or JavaScript-rendered applications; those sources should get dedicated adapters only when permission and terms are clear.

Blocked or restricted platforms such as SEEK, LinkedIn, Indeed, Jora, and Prosple are not auto-crawled. TechAtlas keeps the scheduled loop on enabled registry sources only and does not use browser automation to bypass access controls.
