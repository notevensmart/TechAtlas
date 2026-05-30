# TechAtlas Architecture

TechAtlas V1 is an import-first labour-market intelligence system. The goal is a deployed vertical slice that demonstrates real data ingestion, normalized storage, transparent extraction, analytics APIs, and a usable dashboard.

## System Flow

```text
Permitted CSV/JSONL export
  -> ingestion CLI
  -> row validation
  -> canonical JobRecord
  -> PostgreSQL listings and skills
  -> daily aggregate refresh
  -> FastAPI read API
  -> React dashboard
```

## Backend

The backend is a FastAPI app backed by PostgreSQL and SQLAlchemy 2.x.

Core tables:

- `sources`
- `import_runs`
- `listings`
- `listing_query_matches`
- `skills`
- `listing_skills`
- `daily_skill_snapshots`

Alembic owns schema changes. Taxonomy data is seeded separately from `ingestion/skills_taxonomy.yml`.

## Ingestion

V1 maps every acquisition path into the same canonical job record. The CSV/JSONL importer, configured source crawlers, and source-specific adapters all validate row-level quality, upsert listings, extract skills, and rebuild aggregates after successful imports.

The ingestion boundary is intentionally source-agnostic. A future permitted API, partner feed, public PDF source, or public search-result page can map into the same canonical record without changing the dashboard or analytics API.

## Crawler

The crawler layer is source-agnostic and conservative. It reads explicit seed URLs, checks `robots.txt`, rate limits requests per host, and feeds canonical rows into the existing import service. Adapters handle structured `schema.org/JobPosting` JSON-LD, ATS embedded state, permitted search-result cards, and APS Jobs vacancy PDFs. It is meant for permitted company career pages and structured job sources, not for bypassing job-board restrictions.

## Analytics

V1 reports posting demand by `listed_at`, not import time. Default dashboard range is 30 days, anchored to the latest listing date in the database so historical exports still produce useful views.

Core analytics:

- summary metrics
- skill demand
- skill trend history
- city, role, work mode, and seniority breakdowns
- ranked skill co-occurrence
- paginated listing inspection

## Frontend

The frontend is a React/Vite dashboard. It starts directly in the product experience and uses URL query params for global filters:

- date range
- city
- role family
- skill category
- experience level
- work mode

Tabs organize the V1 surface into Overview, Skills, Relationships, Listings, and Methodology.
