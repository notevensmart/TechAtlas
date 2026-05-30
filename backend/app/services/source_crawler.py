from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import json
import re
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse
import zlib

import httpx
from sqlalchemy.orm import Session

from app.models import CrawlRun, RawJobRecord
from app.services.crawler import (
    CrawlConfig,
    HostRateLimiter,
    LinkParser,
    RobotsPolicy,
    discover_job_links,
    extract_jobposting_nodes,
    map_jobposting_node,
    normalize_url,
)
from app.services.source_registry import SourceDefinition


AU_PATTERNS = (
    r"\baustralia\b",
    r"\bsydney\b",
    r"\bmelbourne\b",
    r"\bbrisbane\b",
    r"\bperth\b",
    r"\badelaide\b",
    r"\bcanberra\b",
    r"\bhobart\b",
    r"\bdarwin\b",
    r"\bgold coast\b",
    r"\bnewcastle\b",
    r"\bwollongong\b",
)

TECH_ROLE_RE = re.compile(
    r"\b("
    r"software|engineer|developer|frontend|front-end|backend|back-end|full[- ]?stack|"
    r"data|analytics|scientist|machine learning|ML|AI|artificial intelligence|"
    r"ICT|information technology|tech career|technology|"
    r"devops|site reliability|SRE|cloud|platform|infrastructure|security|cyber|"
    r"QA|quality engineer|test automation|mobile|ios|android|"
    r"architect|solutions architect|solution engineer|sales engineer|support engineer|"
    r"salesforce|database|BI|LLM|generative AI"
    r")\b",
    re.IGNORECASE,
)


@dataclass
class ExtractedJobRecord:
    source_key: str
    adapter: str
    source_url: str
    external_id: str
    observed_at: datetime
    content_hash: str
    raw_payload: dict[str, Any]
    canonical_row: dict[str, object]


@dataclass
class SourceCrawlResult:
    source: SourceDefinition
    visited_urls: list[str]
    skipped_urls: list[str]
    records: list[ExtractedJobRecord]

    @property
    def pages_fetched(self) -> int:
        return len(self.visited_urls)

    @property
    def pages_skipped(self) -> int:
        return len(self.skipped_urls)


class MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        attr_map = {name.lower(): value for name, value in attrs if value is not None}
        key = attr_map.get("property") or attr_map.get("name")
        content = attr_map.get("content")
        if key and content:
            self.values[key] = content


def _clean_html_text(value: Any) -> str:
    text = unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _strip_tags(value: str) -> str:
    return _clean_html_text(value)


def _absolute_url(base_url: str, href: str) -> str:
    parsed = urlparse(href)
    if parsed.scheme and parsed.netloc:
        return href
    base = urlparse(base_url)
    if href.startswith("/"):
        return f"{base.scheme}://{base.netloc}{href}"
    path = base.path.rsplit("/", 1)[0]
    return f"{base.scheme}://{base.netloc}{path}/{href}"


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _extract_script_assignment(html: str, assignment_name: str) -> dict[str, Any] | None:
    index = html.find(assignment_name)
    if index < 0:
        return None
    start = html.find("{", index)
    if start < 0:
        return None
    raw = _json_object_at(html, start)
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _json_object_at(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _meta_values(html: str) -> dict[str, str]:
    parser = MetaParser()
    parser.feed(html)
    return parser.values


def _url_external_id(url: str) -> str:
    parsed = urlparse(url)
    match = re.search(r"/jobs?/([^/?#]+)", parsed.path)
    if match:
        return match.group(1)
    parts = [part for part in parsed.path.split("/") if part]
    if parts:
        return parts[-1]
    return sha256(url.encode("utf-8")).hexdigest()[:24]


def _path_parts(url: str) -> list[str]:
    return [unquote(part) for part in urlparse(url).path.split("/") if part]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or sha256(value.encode("utf-8")).hexdigest()[:10]


def _payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def _decode_pdf_literal(raw: bytes) -> str:
    value = bytearray()
    index = 0
    while index < len(raw):
        char = raw[index]
        if char == 92 and index + 1 < len(raw):
            next_char = raw[index + 1]
            if next_char in b"nrtbf":
                value.extend({110: b"\n", 114: b"\r", 116: b"\t", 98: b"\b", 102: b"\f"}[next_char])
                index += 2
                continue
            if 48 <= next_char <= 55:
                octal = bytes(raw[index + 1 : index + 4])
                match = re.match(rb"[0-7]{1,3}", octal)
                if match:
                    value.append(int(match.group(0), 8))
                    index += 1 + len(match.group(0))
                    continue
            value.append(next_char)
            index += 2
            continue
        value.append(char)
        index += 1
    return value.decode("latin1", errors="ignore")


def _extract_simple_pdf_text(content: bytes) -> str:
    chunks: list[str] = []
    for stream_match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", content, re.S):
        stream = stream_match.group(1).strip()
        try:
            decoded = zlib.decompress(stream)
        except zlib.error:
            continue

        for literal in re.finditer(rb"\((.*?)\)\s*Tj", decoded, re.S):
            chunks.append(_decode_pdf_literal(literal.group(1)))

        for array in re.finditer(rb"\[(.*?)\]\s*TJ", decoded, re.S):
            parts = [_decode_pdf_literal(part) for part in re.findall(rb"\((.*?)\)", array.group(1), re.S)]
            if parts:
                chunks.append("".join(parts))

    text = "\n".join(chunk.strip() for chunk in chunks if chunk.strip())
    text = text.replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", text)


def _record_from_row(
    *,
    source: SourceDefinition,
    adapter: str,
    source_url: str,
    raw_payload: dict[str, Any],
    row: dict[str, object],
    observed_at: datetime,
) -> ExtractedJobRecord:
    row = dict(row)
    row["source"] = source.key
    row["observed_at"] = observed_at.isoformat()
    content_hash = _payload_hash(raw_payload)
    row["content_hash"] = content_hash
    return ExtractedJobRecord(
        source_key=source.key,
        adapter=adapter,
        source_url=source_url,
        external_id=str(row["external_id"]),
        observed_at=observed_at,
        content_hash=content_hash,
        raw_payload=raw_payload,
        canonical_row=row,
    )


def _contains_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _contains_keyword(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(keyword.lower() in lower for keyword in keywords)


def row_matches_source_filters(source: SourceDefinition, row: dict[str, object]) -> bool:
    title = str(row.get("title") or "")
    location = str(row.get("location") or "")
    description = str(row.get("description") or "")
    combined = f"{title}\n{location}\n{description}"

    if source.filters.country == "AU":
        location_lower = location.strip().lower()
        if location_lower and location_lower != "unknown" and "remote" not in location_lower:
            if not _contains_pattern(location, AU_PATTERNS):
                return False
        elif not _contains_pattern(combined, AU_PATTERNS):
            return False
    if source.filters.tech_only and not TECH_ROLE_RE.search(title):
        return False
    if source.filters.include_keywords and not _contains_keyword(combined, source.filters.include_keywords):
        return False
    if source.filters.exclude_keywords and _contains_keyword(combined, source.filters.exclude_keywords):
        return False
    return True


class BaseAdapter:
    name = "generic-jsonld"

    def can_process_response(self, source: SourceDefinition, url: str, content_type: str, content: bytes) -> bool:
        return "text/html" in content_type.lower()

    def discover_links(self, source: SourceDefinition, url: str, html: str) -> list[str]:
        return discover_job_links(url, html)

    def extract_response_records(
        self,
        source: SourceDefinition,
        url: str,
        response: httpx.Response,
        observed_at: datetime,
    ) -> list[ExtractedJobRecord]:
        return self.extract_records(source, url, response.text, observed_at)

    def extract_records(
        self,
        source: SourceDefinition,
        url: str,
        html: str,
        observed_at: datetime,
    ) -> list[ExtractedJobRecord]:
        records = []
        for node in extract_jobposting_nodes(html):
            row = map_jobposting_node(node, url)
            if row is None or not row_matches_source_filters(source, row):
                continue
            records.append(
                _record_from_row(
                    source=source,
                    adapter=self.name,
                    source_url=url,
                    raw_payload={"kind": "jsonld", "node": node},
                    row=row,
                    observed_at=observed_at,
                )
            )
        return records


class LeverAdapter(BaseAdapter):
    name = "lever-html"

    def discover_links(self, source: SourceDefinition, url: str, html: str) -> list[str]:
        parser = LinkParser(url)
        parser.feed(html)
        links = []
        for link in parser.links:
            parsed = urlparse(link)
            if parsed.netloc != "jobs.lever.co":
                continue
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 2:
                links.append(link)
        return sorted(set(links))


class GreenhouseAdapter(BaseAdapter):
    name = "greenhouse-html"

    def discover_links(self, source: SourceDefinition, url: str, html: str) -> list[str]:
        payload = _extract_script_assignment(html, "window.__remixContext")
        if not payload:
            return []

        links: set[str] = set()
        for node in _walk_dicts(payload):
            job_posts = node.get("jobPosts")
            if not isinstance(job_posts, dict):
                continue
            data = job_posts.get("data")
            if not isinstance(data, list):
                continue
            for item in data:
                if not isinstance(item, dict):
                    continue
                absolute_url = str(item.get("absolute_url") or "").strip()
                summary_row = {
                    "title": item.get("title") or "",
                    "location": item.get("location") or "",
                    "description": item.get("department", {}).get("name") if isinstance(item.get("department"), dict) else "",
                }
                if absolute_url and row_matches_source_filters(source, summary_row):
                    normalized = normalize_url(absolute_url)
                    if normalized:
                        links.add(normalized)
        return sorted(links)

    def extract_records(
        self,
        source: SourceDefinition,
        url: str,
        html: str,
        observed_at: datetime,
    ) -> list[ExtractedJobRecord]:
        records = []
        payload = _extract_script_assignment(html, "window.__remixContext")
        if not payload:
            return records

        meta = _meta_values(html)
        for node in _walk_dicts(payload):
            if node.get("post_type") != "job_post":
                continue
            title = str(node.get("title") or meta.get("og:title") or "").strip()
            description = _clean_html_text(node.get("content") or meta.get("og:description") or "")
            location = str(node.get("job_post_location") or meta.get("og:description") or "Unknown").strip()
            listed_at = str(node.get("published_at") or "").strip()
            if not title or not description or not listed_at:
                continue

            source_url = str(node.get("public_url") or meta.get("og:url") or url).strip()
            external_id = _url_external_id(source_url or url)
            row: dict[str, object] = {
                "source": source.key,
                "external_id": external_id,
                "title": title,
                "company": str(node.get("company_name") or "Unknown").strip(),
                "location": location,
                "description": description,
                "listed_at": listed_at,
                "source_url": source_url or url,
                "work_type": None if node.get("employment") == "hidden" else node.get("employment"),
                "role_hint": title,
            }
            if not row_matches_source_filters(source, row):
                continue
            records.append(
                _record_from_row(
                    source=source,
                    adapter=self.name,
                    source_url=source_url or url,
                    raw_payload={"kind": "greenhouse-remix", "jobPost": node},
                    row=row,
                    observed_at=observed_at,
                )
            )
        return records


class AshbyAdapter(BaseAdapter):
    name = "ashby-html"

    def discover_links(self, source: SourceDefinition, url: str, html: str) -> list[str]:
        payload = _extract_script_assignment(html, "window.__appData")
        if not payload:
            return []

        job_board = payload.get("jobBoard")
        if not isinstance(job_board, dict):
            return []
        postings = job_board.get("jobPostings")
        if not isinstance(postings, list):
            return []

        parts = _path_parts(url)
        if not parts:
            return []
        board_base = f"{urlparse(url).scheme}://{urlparse(url).netloc}/{quote(parts[0])}"

        links = set()
        for posting in postings:
            if not isinstance(posting, dict) or not posting.get("isListed", True):
                continue
            location_parts = [str(posting.get("locationName") or "")]
            secondary = posting.get("secondaryLocations") or posting.get("secondaryLocationNames") or []
            if isinstance(secondary, list):
                location_parts.extend(str(item.get("locationName") if isinstance(item, dict) else item) for item in secondary)
            summary_row = {
                "title": posting.get("title") or "",
                "location": ", ".join(part for part in location_parts if part),
                "description": posting.get("departmentName") or posting.get("teamName") or "",
            }
            if not row_matches_source_filters(source, summary_row):
                continue
            posting_id = str(posting.get("id") or "").strip()
            if posting_id:
                links.add(f"{board_base}/{posting_id}")
        return sorted(links)

    def extract_records(
        self,
        source: SourceDefinition,
        url: str,
        html: str,
        observed_at: datetime,
    ) -> list[ExtractedJobRecord]:
        payload = _extract_script_assignment(html, "window.__appData")
        records = self._extract_from_app_data(source, url, payload, observed_at) if payload else []
        if records:
            return records
        return super().extract_records(source, url, html, observed_at)

    def _extract_from_app_data(
        self,
        source: SourceDefinition,
        url: str,
        payload: dict[str, Any],
        observed_at: datetime,
    ) -> list[ExtractedJobRecord]:
        posting = payload.get("posting")
        organization = payload.get("organization")
        if not isinstance(posting, dict):
            return []

        title = str(posting.get("title") or "").strip()
        description = _clean_html_text(
            posting.get("descriptionHtml")
            or posting.get("descriptionPlainText")
            or posting.get("shortDescription")
            or ""
        )
        listed_at = str(posting.get("publishedDate") or posting.get("updatedAt") or "").strip()
        if not title or not description or not listed_at:
            return []

        locations = [str(posting.get("locationName") or "").strip()]
        secondary_names = posting.get("secondaryLocationNames")
        if isinstance(secondary_names, list):
            locations.extend(str(item).strip() for item in secondary_names)
        location = ", ".join(location for location in locations if location) or "Unknown"
        if posting.get("isRemote") and not location:
            location = "Remote"

        company = "Unknown"
        if isinstance(organization, dict):
            company = str(organization.get("name") or organization.get("publicName") or "Unknown").strip()

        work_mode = str(posting.get("workplaceType") or "").lower() or None
        if work_mode == "on site":
            work_mode = "onsite"

        row: dict[str, object] = {
            "source": source.key,
            "external_id": str(posting.get("id") or _url_external_id(url)),
            "title": title,
            "company": company,
            "location": location,
            "description": description,
            "listed_at": listed_at,
            "source_url": url,
            "work_mode": work_mode,
            "work_type": posting.get("employmentType"),
            "role_hint": title,
        }
        if not row_matches_source_filters(source, row):
            return []
        return [
            _record_from_row(
                source=source,
                adapter=self.name,
                source_url=url,
                raw_payload={"kind": "ashby-app-data", "posting": posting, "organization": organization},
                row=row,
                observed_at=observed_at,
            )
        ]


class CareerOneSearchAdapter(BaseAdapter):
    name = "careerone-search"

    def discover_links(self, source: SourceDefinition, url: str, html: str) -> list[str]:
        # CareerOne robots.txt disallows /jobview/ detail pages, so this adapter
        # intentionally stays on search-result pages only.
        links: set[str] = set()
        for match in re.finditer(r'href="([^"]*?page=(\d+)[^"]*)"', html):
            page = int(match.group(2))
            if 1 < page <= 3:
                links.add(_absolute_url(url, unescape(match.group(1))))
        return sorted(links)

    def extract_records(
        self,
        source: SourceDefinition,
        url: str,
        html: str,
        observed_at: datetime,
    ) -> list[ExtractedJobRecord]:
        records: list[ExtractedJobRecord] = []
        for card in re.split(r'<div page-section="Search"', html)[1:]:
            row = self._row_from_card(source, url, card, observed_at)
            if row is None or not row_matches_source_filters(source, row):
                continue
            records.append(
                _record_from_row(
                    source=source,
                    adapter=self.name,
                    source_url=str(row["source_url"]),
                    raw_payload={"kind": "careerone-search-card", "html": card[:5000]},
                    row=row,
                    observed_at=observed_at,
                )
            )
        return records

    def _row_from_card(
        self,
        source: SourceDefinition,
        page_url: str,
        card: str,
        observed_at: datetime,
    ) -> dict[str, object] | None:
        href_match = re.search(r'href="([^"]*/jobview/[^"]+)"[^>]+title="([^"]+)"', card)
        if not href_match:
            return None

        source_url = _absolute_url(page_url, unescape(href_match.group(1))).split("?")[0]
        title = _strip_tags(unescape(href_match.group(2)))
        external_id_match = re.search(r"/jobview/[^/]+/([^/?#]+)", source_url)
        external_id = external_id_match.group(1) if external_id_match else _url_external_id(source_url)

        date_match = re.search(r'<div[^>]+class="[^"]*\bjob-date\b[^"]*"[^>]*>\s*(.*?)\s*</div>', card, re.S)
        listed_at = self._parse_relative_posted_at(_strip_tags(date_match.group(1)) if date_match else "", observed_at)
        if listed_at is None:
            return None

        company = "Unknown"
        brand_match = re.search(r'<div brand="([^"]+)"', card)
        if brand_match:
            company = _strip_tags(unescape(brand_match.group(1)))
        else:
            company_match = re.search(r'<a[^>]+/jobs/br_[^"]+"[^>]+title="([^"]+)"', card)
            if company_match:
                company = _strip_tags(unescape(company_match.group(1)))

        locations = [
            _strip_tags(unescape(item))
            for item in re.findall(r'<a[^>]+href="/jobs/in-[^"]+"[^>]+title="([^"]+)"', card)
        ]
        location = ", ".join(dict.fromkeys(locations)) or "Australia"

        work_type = None
        work_match = re.search(
            r'<div class="d-inline-block[^"]*text-truncate[^"]*"[^>]*>\s*(<span.*?</span>\s*<span.*?</span>)',
            card,
            re.S,
        )
        if work_match:
            work_type = _strip_tags(work_match.group(1)).replace(" · ", "; ")

        key_points = []
        key_section = re.search(r"Key points we found(.*?)(?:</ul>|</div>\s*</div>\s*</div>)", card, re.S)
        if key_section:
            key_points = [
                _strip_tags(point)
                for point in re.findall(r"<li[^>]*>(.*?)</li>", key_section.group(1), re.S)
                if _strip_tags(point)
            ]
        if not key_points:
            text = _strip_tags(card)
            after_title = text.split(title, 1)[-1] if title in text else text
            key_points = [after_title[:900]]

        description = " ".join(
            part
            for part in [
                title,
                company,
                location,
                " ".join(key_points[:4]),
            ]
            if part
        )
        if len(description) < 80:
            return None

        return {
            "source": source.key,
            "external_id": external_id,
            "title": title,
            "company": company,
            "location": location,
            "description": description,
            "listed_at": listed_at.isoformat(),
            "source_url": source_url,
            "work_type": work_type,
            "role_hint": title,
        }

    def _parse_relative_posted_at(self, value: str, observed_at: datetime) -> datetime | None:
        text = value.strip().lower()
        if not text.startswith("posted"):
            return None
        if "today" in text or "just now" in text:
            return observed_at
        match = re.search(r"posted\s+(\d+)\s*d\s+ago", text)
        if match:
            return observed_at - timedelta(days=int(match.group(1)))
        match = re.search(r"posted\s+(\d+)\s*day", text)
        if match:
            return observed_at - timedelta(days=int(match.group(1)))
        return None


class ApsJobsPdfAdapter(BaseAdapter):
    name = "apsjobs-pdf"
    _labels = {
        "salary",
        "opportunity type",
        "opportunity status",
        "opportunity employment type",
        "opportunity employment type details",
        "aps classification",
        "position reference",
        "closing date",
        "job category",
        "office arrangement",
        "security clearance",
        "contact officer",
        "contact phone",
        "contact email",
        "agency employment act",
        "website",
        "recruitment portal link",
        "vacancy number",
    }

    def can_process_response(self, source: SourceDefinition, url: str, content_type: str, content: bytes) -> bool:
        parsed = urlparse(url)
        return (
            parsed.netloc.lower() == "www.apsjobs.gov.au"
            and "aps_VacancyDetailPage" in parsed.path
            and ("application/pdf" in content_type.lower() or content.startswith(b"%PDF"))
        )

    def discover_links(self, source: SourceDefinition, url: str, html: str) -> list[str]:
        return []

    def extract_response_records(
        self,
        source: SourceDefinition,
        url: str,
        response: httpx.Response,
        observed_at: datetime,
    ) -> list[ExtractedJobRecord]:
        text = _extract_simple_pdf_text(response.content)
        row = self._row_from_text(source, str(response.url), text, observed_at)
        if row is None or not row_matches_source_filters(source, row):
            return []
        return [
            _record_from_row(
                source=source,
                adapter=self.name,
                source_url=str(response.url),
                raw_payload={"kind": "apsjobs-pdf", "text": text[:12000]},
                row=row,
                observed_at=observed_at,
            )
        ]

    def _row_from_text(
        self,
        source: SourceDefinition,
        url: str,
        text: str,
        observed_at: datetime,
    ) -> dict[str, object] | None:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 10:
            return None

        field_values = self._field_values(lines)
        title_index = self._title_index(lines)
        if title_index is None:
            return None

        title = lines[title_index]
        company = self._nearest_company(lines, title_index)
        location = self._nearest_location(lines, title_index) or "Australia"
        description = self._description(lines, title_index, field_values)
        if not title or not company or len(description) < 100:
            return None

        vacancy_id = parse_qs(urlparse(url).query).get("id", [_url_external_id(url)])[0]
        salary_min, salary_max = self._salary_range(field_values.get("salary", ""))
        work_mode = self._work_mode(field_values.get("office arrangement"))
        work_type = field_values.get("opportunity type")

        listed_at = self._listed_at(field_values, observed_at)

        return {
            "source": source.key,
            "external_id": vacancy_id,
            "title": title,
            "company": company,
            "location": location,
            "description": description,
            "listed_at": listed_at.isoformat(),
            "source_url": url,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_period": "annual" if salary_min or salary_max else None,
            "work_mode": work_mode,
            "work_type": work_type,
            "role_hint": title,
        }

    def _field_values(self, lines: list[str]) -> dict[str, str]:
        values: dict[str, str] = {}
        for index, line in enumerate(lines):
            label = line.lower()
            if label not in self._labels:
                continue
            parts = []
            for candidate in lines[index + 1 : index + 6]:
                if candidate.lower() in self._labels:
                    break
                parts.append(candidate)
            if parts:
                values[label] = " ".join(parts).strip()
        return values

    def _title_index(self, lines: list[str]) -> int | None:
        for index in range(1, len(lines) - 1):
            line = lines[index]
            if line.lower() in self._labels or len(line) > 140:
                continue
            if TECH_ROLE_RE.search(line) and self._nearest_location(lines, index):
                return index
        return None

    def _nearest_company(self, lines: list[str], title_index: int) -> str:
        for index in range(title_index - 1, max(-1, title_index - 6), -1):
            line = lines[index]
            if line.lower() not in self._labels and not _contains_pattern(line, AU_PATTERNS):
                return line
        return "Australian Public Service"

    def _nearest_location(self, lines: list[str], title_index: int) -> str | None:
        for line in lines[title_index + 1 : title_index + 5]:
            if _contains_pattern(line, AU_PATTERNS) or re.search(r"\b(ACT|NSW|VIC|QLD|SA|WA|TAS|NT)\b", line):
                return line
        return None

    def _description(self, lines: list[str], title_index: int, fields: dict[str, str]) -> str:
        body = " ".join(lines[title_index + 2 : title_index + 80])
        prefix = " ".join(
            part
            for part in [
                fields.get("job category"),
                fields.get("aps classification"),
                fields.get("opportunity status"),
            ]
            if part
        )
        return re.sub(r"\s+", " ", f"{prefix} {body}").strip()

    def _salary_range(self, value: str) -> tuple[int | None, int | None]:
        amounts = [int(amount.replace(",", "")) for amount in re.findall(r"\$?\s*([0-9][0-9,]{4,})", value)]
        if not amounts:
            return None, None
        return min(amounts), max(amounts)

    def _work_mode(self, value: str | None) -> str | None:
        text = (value or "").lower()
        if "hybrid" in text:
            return "hybrid"
        if "remote" in text:
            return "remote"
        if "on site" in text or "onsite" in text:
            return "onsite"
        return None

    def _listed_at(self, fields: dict[str, str], observed_at: datetime) -> datetime:
        for key in ("date advertised", "published", "opening date"):
            value = fields.get(key)
            if not value:
                continue
            for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(value.split()[0], pattern).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
        return observed_at


ADAPTERS: dict[str, type[BaseAdapter]] = {
    "generic-jsonld": BaseAdapter,
    "apsjobs-pdf": ApsJobsPdfAdapter,
    "ashby-html": AshbyAdapter,
    "careerone-search": CareerOneSearchAdapter,
    "lever-html": LeverAdapter,
    "greenhouse-html": GreenhouseAdapter,
}


@dataclass(frozen=True)
class DiscoveredSource:
    key: str
    adapter: str
    seed: str
    reason: str


def detect_source_from_url(url: str, html: str | None = None) -> DiscoveredSource | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    parts = _path_parts(url)
    if host == "jobs.lever.co" and parts:
        return DiscoveredSource(f"lever:{_slug(parts[0])}", "lever-html", f"{parsed.scheme}://{host}/{quote(parts[0])}", "lever-host")
    if host in {"job-boards.greenhouse.io", "job-boards.eu.greenhouse.io"} and parts:
        return DiscoveredSource(
            f"greenhouse:{_slug(parts[0])}",
            "greenhouse-html",
            f"{parsed.scheme}://{host}/{quote(parts[0])}",
            "greenhouse-host",
        )
    if host == "jobs.ashbyhq.com" and parts:
        return DiscoveredSource(
            f"ashby:{_slug(parts[0])}",
            "ashby-html",
            f"{parsed.scheme}://{host}/{quote(parts[0])}",
            "ashby-host",
        )
    if html and extract_jobposting_nodes(html):
        return DiscoveredSource(f"generic:{_slug(host)}", "generic-jsonld", url, "jobposting-jsonld")
    return None


class SourceScout:
    def __init__(self, config: CrawlConfig | None = None) -> None:
        self.config = config or CrawlConfig()

    def scout(self, seed_urls: list[str]) -> list[DiscoveredSource]:
        queue: deque[str] = deque()
        for seed in seed_urls:
            normalized = normalize_url(seed)
            if normalized:
                queue.append(normalized)

        seen: set[str] = set()
        discovered: dict[str, DiscoveredSource] = {}
        limiter = HostRateLimiter(self.config.request_delay_seconds)
        with httpx.Client(
            timeout=self.config.timeout_seconds,
            follow_redirects=True,
            verify=self.config.verify_tls,
        ) as client:
            robots = RobotsPolicy(client, self.config)
            while queue and len(seen) < self.config.max_urls:
                url = queue.popleft()
                normalized = normalize_url(url)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                if not robots.allowed(normalized):
                    continue

                limiter.wait(normalized)
                try:
                    response = client.get(normalized, headers={"User-Agent": self.config.user_agent})
                except httpx.HTTPError:
                    continue
                content_type = response.headers.get("content-type", "")
                if response.status_code >= 400 or "text/html" not in content_type:
                    continue

                final_url = str(response.url)
                html = response.text
                candidate = detect_source_from_url(final_url, html)
                if candidate:
                    discovered[candidate.key] = candidate

                parser = LinkParser(final_url)
                parser.feed(html)
                for link in parser.links:
                    candidate = detect_source_from_url(link)
                    if candidate:
                        discovered[candidate.key] = candidate
                    parsed_link = urlparse(link)
                    parsed_seed = urlparse(final_url)
                    if (
                        parsed_link.netloc == parsed_seed.netloc
                        and link not in seen
                        and any(hint in parsed_link.path.lower() for hint in ("career", "job", "opening"))
                        and len(seen) + len(queue) < self.config.max_urls
                    ):
                        queue.append(link)
        return sorted(discovered.values(), key=lambda item: item.key)


def discovered_sources_to_registry(sources: list[DiscoveredSource]) -> dict[str, list[dict[str, Any]]]:
    return {
        "sources": [
            {
                "key": source.key,
                "adapter": source.adapter,
                "enabled": True,
                "seeds": [source.seed],
                "discover_depth": 1,
                "max_urls": 100,
                "filters": {"country": "AU", "tech_only": True},
                "compliance_note": f"Discovered from public careers HTML ({source.reason}); crawler obeys robots.txt and rate limits.",
            }
            for source in sources
        ]
    }


class SourceCrawler:
    def __init__(self, config: CrawlConfig | None = None) -> None:
        self.config = config or CrawlConfig()

    def crawl_source(self, source: SourceDefinition) -> SourceCrawlResult:
        adapter_class = ADAPTERS.get(source.adapter)
        if adapter_class is None:
            raise ValueError(f"unknown crawler adapter: {source.adapter}")
        adapter = adapter_class()

        max_urls = source.max_urls or self.config.max_urls
        queue: deque[tuple[str, int]] = deque()
        for seed in source.seeds:
            normalized = normalize_url(seed)
            if normalized:
                queue.append((normalized, 0))

        seen: set[str] = set()
        visited: list[str] = []
        skipped: list[str] = []
        records: list[ExtractedJobRecord] = []

        limiter = HostRateLimiter(self.config.request_delay_seconds)
        with httpx.Client(
            timeout=self.config.timeout_seconds,
            follow_redirects=True,
            verify=self.config.verify_tls,
        ) as client:
            robots = RobotsPolicy(client, self.config)
            while queue and len(visited) < max_urls:
                url, depth = queue.popleft()
                normalized = normalize_url(url)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)

                if not robots.allowed(normalized):
                    skipped.append(normalized)
                    continue

                limiter.wait(normalized)
                try:
                    response = client.get(normalized, headers={"User-Agent": self.config.user_agent})
                except httpx.HTTPError:
                    skipped.append(normalized)
                    continue

                content_type = response.headers.get("content-type", "")
                if response.status_code >= 400 or not adapter.can_process_response(
                    source, normalized, content_type, response.content
                ):
                    skipped.append(normalized)
                    continue

                final_url = str(response.url)
                visited.append(final_url)
                observed_at = datetime.now(timezone.utc)
                records.extend(adapter.extract_response_records(source, final_url, response, observed_at))

                if "text/html" in content_type.lower() and depth < source.discover_depth:
                    html = response.text
                    for link in adapter.discover_links(source, final_url, html):
                        if link not in seen and len(seen) + len(queue) < max_urls:
                            queue.append((link, depth + 1))

        return SourceCrawlResult(source=source, visited_urls=visited, skipped_urls=skipped, records=records)


def create_crawl_run(session: Session, source: SourceDefinition) -> CrawlRun:
    run = CrawlRun(
        source_key=source.key,
        adapter=source.adapter,
        status="running",
        seed_count=len(source.seeds),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def persist_raw_records(session: Session, crawl_run_id: int, result: SourceCrawlResult) -> int:
    seen: set[tuple[str, str, str]] = set()
    count = 0
    for record in result.records:
        key = (record.source_key, record.external_id, record.content_hash)
        if key in seen:
            continue
        seen.add(key)
        session.add(
            RawJobRecord(
                crawl_run_id=crawl_run_id,
                source_key=record.source_key,
                adapter=record.adapter,
                external_id=record.external_id,
                source_url=record.source_url,
                observed_at=record.observed_at,
                content_hash=record.content_hash,
                raw_payload=record.raw_payload,
                canonical_payload=record.canonical_row,
            )
        )
        count += 1
    session.commit()
    return count


def finish_crawl_run(
    session: Session,
    crawl_run_id: int,
    *,
    status: str,
    result: SourceCrawlResult | None = None,
    rows_imported: int = 0,
    error_message: str | None = None,
) -> None:
    run = session.get(CrawlRun, crawl_run_id)
    if run is None:
        return
    run.status = status
    run.finished_at = datetime.now(timezone.utc)
    run.error_message = error_message
    run.rows_imported = rows_imported
    if result is not None:
        run.pages_fetched = result.pages_fetched
        run.pages_skipped = result.pages_skipped
        run.rows_extracted = len(result.records)
    session.commit()
