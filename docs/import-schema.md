# Import Schema

TechAtlas V1 imports real, permitted CSV or JSONL job-posting data. It does not include demo or synthetic listing data.

## Required Fields

| Field | Type | Description |
|---|---|---|
| `source` | string | Source name, such as a permitted export provider. |
| `external_id` | string | Stable listing ID. A canonical listing URL may be used if no numeric ID exists. |
| `title` | string | Job title. |
| `company` | string | Hiring company or advertiser. |
| `location` | string | Raw location text. |
| `description` | string | Job description text used for skill extraction. |
| `listed_at` | datetime | ISO timestamp or date for when the job was listed. |

## Optional Fields

| Field | Type | Description |
|---|---|---|
| `source_url` | string | Canonical source listing URL. |
| `salary_min` | integer | Visible salary lower bound. |
| `salary_max` | integer | Visible salary upper bound. |
| `salary_period` | string | `annual`, `monthly`, `weekly`, `daily`, or `hourly`. Defaults to annual when salary exists. |
| `work_mode` | string | `remote`, `hybrid`, `onsite`, or source-specific text to infer from. |
| `work_type` | string | Full-time, contract, part-time, casual, etc. |
| `role_hint` | string | Source/search category hint, such as `ai engineer` or `backend developer`. |

## CSV Example

```csv
source,external_id,title,company,location,description,listed_at,salary_min,salary_max,salary_period,role_hint
permitted-export,job-001,AI Engineer,Example Co,Sydney NSW,"Build RAG systems with Python and AWS.",2026-05-01T00:00:00Z,120000,150000,annual,ai engineer
```

## JSONL Example

```jsonl
{"source":"permitted-export","external_id":"job-001","title":"AI Engineer","company":"Example Co","location":"Sydney NSW","description":"Build RAG systems with Python and AWS.","listed_at":"2026-05-01T00:00:00Z","salary_min":120000,"salary_max":150000,"salary_period":"annual","role_hint":"ai engineer"}
```

## Validation Behavior

- Missing required columns in CSV fail the import before database writes.
- Invalid rows are skipped and reported.
- Valid rows are imported even when some rows fail.
- The command fails if no rows are valid.
- Listings are upserted by `source + external_id`.

## JobDataAPI Sync

TechAtlas can also fetch recent Australian postings from JobDataAPI and map them into this canonical schema.

Required environment variable:

```env
JOBDATA_API_KEY=your_api_key_here
```

Command:

```bash
python -m ingestion.cli sync-jobdata --days 30 --max-pages 3 --raw-output data/jobdata_raw.jsonl --rejects rejected_rows.csv
```

Mapping notes:

- `id` or `ext_id` becomes `external_id`.
- `description_string` is preferred over raw HTML description.
- salary fields are imported only when `salary_currency` is `AUD` or blank.
- `work_mode` maps `1` to hybrid and `2`/`3` to remote.
- raw API jobs can be written to JSONL for audit with `--raw-output`.
