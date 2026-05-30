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

## Implemented Adapter

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
