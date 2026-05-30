# TechAtlas

Australian tech job market intelligence for real, permitted job-posting exports.

TechAtlas V1 is a recruiter-facing full-stack analytics project. It imports real CSV/JSONL job data or crawls configured public careers pages, stores it in PostgreSQL, extracts skills through a transparent taxonomy, and serves market demand insights through a FastAPI API and React dashboard.

## What V1 Does

- Imports permitted real job-posting data with a CLI.
- Crawls configured public careers/job pages with local HTML, search-result, and PDF adapters.
- Stores raw extracted source records for audit and reprocessing.
- Validates rows and writes a rejected-row report for bad records.
- Deduplicates listings by `source + external_id`.
- Tracks listing freshness with `first_seen_at` and `last_seen_at`.
- Extracts skills from titles and descriptions with a YAML taxonomy.
- Normalizes city, work mode, seniority, role family, and salary fields.
- Computes demand, trend, breakdown, and co-occurrence analytics.
- Exposes a public read-only API under `/api/v1`.
- Renders a light-theme dashboard with URL-synced filters.

V1 does not ship demo or synthetic listings. It also does not ship a SEEK crawler by default; source access rules can change, and the product is designed around compliant imports and configured source adapters.

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.x, Pydantic |
| Database | PostgreSQL, Alembic |
| Ingestion | Python CLI, CSV/JSONL importer, source adapters |
| Frontend | React, TypeScript, Vite |
| Charts | Recharts |
| Styling | Tailwind CSS |
| Deployment | Railway backend/Postgres, Vercel frontend |
| Local DB | Docker Compose |

## Repository Layout

```text
backend/      FastAPI app, SQLAlchemy models, Alembic migrations, API services
ingestion/    CLI entrypoint and YAML skills taxonomy
frontend/     React dashboard
docs/         Architecture, methodology, import schema, roadmap
```

## Local Setup

Start Postgres:

```bash
docker compose up -d postgres
```

Set up the backend:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

Set up the frontend:

```bash
cd frontend
npm install
npm run dev
```

The dashboard runs at `http://localhost:5173`; the API runs at `http://localhost:8000`.

## Import Real Data

From the repository root:

```bash
python -m ingestion.cli import path/to/jobs.csv --rejects rejected_rows.csv
```

Seed skills manually if needed:

```bash
python -m ingestion.cli seed-skills
```

Rebuild aggregates manually if needed:

```bash
python -m ingestion.cli refresh-aggregates
```

Required import fields are documented in [docs/import-schema.md](docs/import-schema.md).

## Crawl Configured Careers Sources

TechAtlas can run its own local acquisition layer from [ingestion/sources.yml](ingestion/sources.yml). This does not require paid APIs. The current adapters use permitted public pages and source-specific parsing intelligence:

- `lever-html`: discovers Lever board postings and extracts structured posting data.
- `greenhouse-html`: reads Greenhouse board/detail HTML and extracts embedded job state.
- `ashby-html`: reads Ashby board/detail HTML and extracts embedded posting state.
- `generic-jsonld`: extracts `schema.org/JobPosting` JSON-LD from permitted pages.
- `careerone-search`: imports CareerOne search-result cards without requesting disallowed detail pages.
- `apsjobs-pdf`: imports public APS Jobs vacancy detail PDFs from known `aps_VacancyDetailPage` URLs.

Platform feasibility notes are documented in [docs/platform_adapters.md](docs/platform_adapters.md).

Run all enabled sources:

```bash
python -m ingestion.cli crawl-all --canonical-output data/crawl_all_rows.jsonl --rejects-dir data/rejects
```

Run one source while testing:

```bash
python -m ingestion.cli crawl-all --source greenhouse:roller --max-urls 40 --canonical-output data/roller_rows.jsonl
```

Show recent crawler health:

```bash
python -m ingestion.cli source-report
```

Discover supported ATS boards from public careers pages:

```bash
python -m ingestion.cli scout-sources data/careers_seed_urls.txt --output data/discovered_sources.yml
```

If your local Windows CA certificates are broken, use `--insecure-skip-tls-verify` only for local debugging.

## Crawl Ad Hoc Structured Pages

TechAtlas includes crawler logic for permitted sites that expose `schema.org/JobPosting` JSON-LD.

Create a seed file with one URL per line, then run:

```bash
python -m ingestion.cli crawl-structured seeds.txt --max-urls 25 --canonical-output data/crawler_rows.jsonl --rejects rejected_rows.csv
```

Optionally discover same-host job/career links:

```bash
python -m ingestion.cli crawl-structured seeds.txt --discover-depth 1 --max-urls 100 --delay 2
```

See [docs/crawler.md](docs/crawler.md).

## API

Core endpoints:

- `GET /api/v1/health`
- `GET /api/v1/imports/summary`
- `GET /api/v1/stats/summary`
- `GET /api/v1/skills/demand`
- `GET /api/v1/skills/history`
- `GET /api/v1/skills/co-occurrence`
- `GET /api/v1/stats/breakdowns`
- `GET /api/v1/listings`

FastAPI docs are available at `/docs` when the backend is running.

## Testing

Run unit tests:

```bash
pytest
```

Integration tests require a disposable PostgreSQL URL:

```bash
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/techatlas_test pytest
```

Frontend build:

```bash
cd frontend
npm run build
```

## Docs

- [Architecture](docs/architecture.md)
- [Crawler Logic](docs/crawler.md)
- [Import Schema](docs/import-schema.md)
- [Methodology](docs/methodology.md)
- [Roadmap](docs/roadmap.md)
