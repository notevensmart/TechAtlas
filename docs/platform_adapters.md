# Platform Adapter Feasibility

TechAtlas prioritizes direct company ATS boards and job platforms that expose crawlable public pages with stable listing metadata. Broad job boards are evaluated case-by-case against robots.txt and access rules.

## Australia Job Platform Scan

The broad-market leaders are SEEK, Indeed, LinkedIn, Jora, and then a mix of app-store, government, and smaller boards depending on the ranking method. TechAtlas treats app-store pages as non-job platforms and evaluates the next crawlable job boards separately.

| Platform | Status | Reason |
| --- | --- | --- |
| SEEK | Blocked | Robots.txt disallows job detail paths, query/search URLs, GraphQL, and job search API paths for general crawlers. |
| Indeed | Blocked | Job/search surfaces are not suitable for this crawler without explicit platform permission. |
| LinkedIn Jobs | Blocked | LinkedIn explicitly prohibits automated access without express permission. |
| Jora | Blocked | Robots.txt disallows all generic crawlers and job/search paths. |
| CareerOne | Implemented | Search-result pages are crawlable; detail pages are not followed because robots.txt disallows `/jobview/`. |
| APS Jobs | Implemented for detail PDFs | Robots.txt allows crawling. The adapter parses public vacancy detail PDFs from `aps_VacancyDetailPage` URLs. |
| Workforce Australia | Blocked | Robots.txt disallows `/` for generic crawlers. |
| I Work for NSW | Partially feasible | Robots.txt allows search-style crawling, but Cloudflare may block direct non-browser requests. |
| Prosple | Blocked for default crawler | Direct requests to `au.prosple.com/robots.txt` and jobs pages currently return `403`, so TechAtlas should use permitted exports or explicit access instead. |

## Blocked Platforms

Blocked platforms are not represented as covered sources in the product. SEEK, Indeed, LinkedIn Jobs, Jora, Workforce Australia, and Prosple require explicit permission, alternative exports, or a different access model before they should be included in TechAtlas.

This separation is intentional: the dashboard should communicate actual observed coverage, not imply that broad-market job boards are complete.

## Implemented Sources

The Coverage tab and `GET /api/v1/sources/health` report implemented or observed sources from the database, latest crawler runs, raw records, and `ingestion/sources.yml`.

Current implemented adapter families:

- `lever-html`: direct Lever board/detail postings.
- `greenhouse-html`: direct Greenhouse board/detail postings.
- `ashby-html`: direct Ashby board/detail postings.
- `generic-jsonld`: permitted pages exposing `schema.org/JobPosting`.
- `careerone-search`: CareerOne search-result cards only.
- `apsjobs-pdf`: APS Jobs vacancy detail PDFs supplied as public detail URLs.

## Coverage Quality Tiers

- `high`: detail-level ATS, JSON-LD, or parsed PDF sources with stable listing IDs and usable descriptions. Lever, Greenhouse, Ashby, generic JSON-LD, and parsed APS detail PDFs usually land here when rows are extracted successfully.
- `medium`: sources with useful but partial detail. CareerOne search-card records default here because TechAtlas intentionally does not follow disallowed detail pages. APS PDF sources can also be medium when parsed detail is usable but date semantics are limited.
- `low`: failed latest crawls, sources that extracted zero rows, sources with no current listings, or sources whose stored descriptions look too short or incomplete for reliable skill extraction.

## Adapter Notes

`careerone-search` imports list-level job records from CareerOne search result pages. It requires a clear relative posting date, such as `Posted 3d ago`, and intentionally does not request CareerOne detail pages.

This keeps TechAtlas inside V1's real-data-only and compliance-first ingestion model while adding coverage from a well-known Australian job platform.

`apsjobs-pdf` imports public APS Jobs vacancy detail PDFs. APS PDFs generally expose salary, classification, job category, office arrangement, agency, title, location, and description. They do not consistently expose a posted/listed date in the PDF payload, so the adapter uses the crawl observation timestamp as the listing date when no source date is available.

APS source entries should be supplied as known public vacancy detail URLs, for example:

```yaml
sources:
  - key: apsjobs:manual-detail-urls
    adapter: apsjobs-pdf
    enabled: false
    seeds:
      - https://www.apsjobs.gov.au/aps_VacancyDetailPage?id=a05...
    discover_depth: 0
    max_urls: 25
    filters:
      country: AU
      tech_only: true
```
