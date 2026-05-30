from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import json
import re
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.normalization import CANONICAL_QUERIES


DEFAULT_ROLE_QUERIES = CANONICAL_QUERIES


@dataclass
class JobDataSyncResult:
    raw_seen: int
    canonical_rows: list[dict[str, object]]
    raw_output_path: Path | None = None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _first_name(items: Any) -> str | None:
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict):
            value = item.get("name") or item.get("display_name") or item.get("code")
            if value:
                return str(value)
        elif item:
            return str(item)
    return None


def _location(job: dict[str, Any]) -> str:
    if job.get("location_string"):
        return _text(job["location_string"])
    if job.get("location"):
        return _text(job["location"])

    city = _first_name(job.get("cities"))
    state = _first_name(job.get("states"))
    country = _first_name(job.get("countries"))
    parts = [part for part in [city, state, country] if part]
    if parts:
        return ", ".join(parts)

    if job.get("has_remote"):
        return "Remote"
    return "Australia"


def _description(job: dict[str, Any]) -> str:
    value = job.get("description_string") or job.get("description_md") or job.get("description") or ""
    text = unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _company_name(job: dict[str, Any]) -> str:
    company = job.get("company")
    if isinstance(company, dict):
        return _text(company.get("name") or company.get("display_name") or company.get("website_url")) or "Unknown"
    return _text(company) or "Unknown"


def _work_mode(job: dict[str, Any]) -> str | None:
    mode = job.get("work_mode")
    if mode in {1, "1", "HYBRID", "hybrid"}:
        return "hybrid"
    if mode in {2, "2", 3, "3", "REMOTE", "REMOTE_ANY", "remote"}:
        return "remote"
    if job.get("has_remote") is True:
        return "remote"
    return None


def _work_type(job: dict[str, Any]) -> str | None:
    types = job.get("types")
    if not isinstance(types, list):
        return None
    names = []
    for item in types:
        if isinstance(item, dict):
            value = item.get("name") or item.get("label") or item.get("code")
        else:
            value = item
        if value:
            names.append(str(value))
    return ", ".join(names) if names else None


def _salary(job: dict[str, Any]) -> tuple[int | None, int | None, str | None]:
    currency = _text(job.get("salary_currency")).upper()
    if currency and currency != "AUD":
        return None, None, None

    def parse(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(float(str(value).replace(",", "")))
        except ValueError:
            return None

    salary_min = parse(job.get("salary_min"))
    salary_max = parse(job.get("salary_max"))
    if salary_min is None and salary_max is None:
        return None, None, None
    return salary_min, salary_max, "annual"


def map_jobdata_job(job: dict[str, Any], role_hint: str) -> dict[str, object] | None:
    title = _text(job.get("title"))
    description = _description(job)
    published = _text(job.get("published"))
    external_id = _text(job.get("ext_id") or job.get("id"))

    if not title or not description or not published or not external_id:
        return None

    salary_min, salary_max, salary_period = _salary(job)
    row: dict[str, object] = {
        "source": "jobdataapi",
        "external_id": external_id,
        "title": title,
        "company": _company_name(job),
        "location": _location(job),
        "description": description,
        "listed_at": published,
        "source_url": _text(job.get("application_url")) or None,
        "work_mode": _work_mode(job),
        "work_type": _work_type(job),
        "role_hint": role_hint,
    }
    if salary_min is not None:
        row["salary_min"] = salary_min
    if salary_max is not None:
        row["salary_max"] = salary_max
    if salary_period:
        row["salary_period"] = salary_period
    return row


def fetch_jobdata_rows(
    *,
    api_key: str | None = None,
    days: int = 30,
    page_size: int = 200,
    max_pages_per_query: int = 3,
    queries: list[str] | None = None,
    raw_output_path: Path | None = None,
) -> JobDataSyncResult:
    settings = get_settings()
    resolved_key = api_key or settings.jobdata_api_key
    if not resolved_key:
        raise ValueError("JOBDATA_API_KEY is required for JobDataAPI sync")

    role_queries = queries or DEFAULT_ROLE_QUERIES
    headers = {"Authorization": f"Api-Key {resolved_key}"}
    seen_ids: set[str] = set()
    raw_jobs: list[dict[str, Any]] = []
    rows: list[dict[str, object]] = []

    with httpx.Client(timeout=45) as client:
        for role_query in role_queries:
            for page in range(1, max_pages_per_query + 1):
                params = {
                    "title": role_query,
                    "country_code": "AU",
                    "language": "en",
                    "max_age": days,
                    "page": page,
                    "page_size": page_size,
                    "description_str": "true",
                    "location_str": "true",
                }
                response = client.get(settings.jobdata_base_url, headers=headers, params=params)
                response.raise_for_status()
                payload = response.json()
                results = payload.get("results") or []
                if not results:
                    break

                for job in results:
                    if not isinstance(job, dict):
                        continue
                    raw_id = _text(job.get("ext_id") or job.get("id"))
                    if not raw_id or raw_id in seen_ids:
                        continue
                    seen_ids.add(raw_id)
                    raw_jobs.append(job)
                    row = map_jobdata_job(job, role_hint=role_query)
                    if row is not None:
                        rows.append(row)

                if not payload.get("next"):
                    break

    written_path = None
    if raw_output_path:
        raw_output_path.parent.mkdir(parents=True, exist_ok=True)
        with raw_output_path.open("w", encoding="utf-8") as handle:
            for job in raw_jobs:
                handle.write(json.dumps(job, ensure_ascii=True))
                handle.write("\n")
        written_path = raw_output_path

    return JobDataSyncResult(
        raw_seen=len(raw_jobs),
        canonical_rows=rows,
        raw_output_path=written_path,
    )

