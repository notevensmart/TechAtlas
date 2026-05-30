from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import json
import re
import time
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx


JOB_LINK_HINTS = (
    "job",
    "jobs",
    "career",
    "careers",
    "opening",
    "openings",
    "position",
    "positions",
    "greenhouse",
    "lever",
    "workday",
)


@dataclass(frozen=True)
class CrawlConfig:
    user_agent: str = "TechAtlasBot/0.1 (+local portfolio project)"
    request_delay_seconds: float = 1.5
    timeout_seconds: float = 20
    max_urls: int = 100
    discover_depth: int = 0
    obey_robots: bool = True
    allow_on_robots_404: bool = True
    verify_tls: bool = True


@dataclass
class CrawlPage:
    url: str
    status_code: int
    html: str


@dataclass
class CrawlResult:
    visited_urls: list[str]
    skipped_urls: list[str]
    fetched_pages: int
    extracted_rows: list[dict[str, object]]


class JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self._chunks: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        attr_map = {name.lower(): value for name, value in attrs if value is not None}
        script_type = attr_map.get("type", "").lower()
        if "ld+json" in script_type:
            self._capture = True
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._capture:
            self.blocks.append("".join(self._chunks).strip())
            self._capture = False
            self._chunks = []


class LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                absolute = normalize_url(urljoin(self.base_url, value))
                if absolute:
                    self.links.add(absolute)


class RobotsPolicy:
    def __init__(self, client: httpx.Client, config: CrawlConfig) -> None:
        self.client = client
        self.config = config
        self._cache: dict[str, RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        if not self.config.obey_robots:
            return True

        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._cache:
            self._cache[origin] = self._load(origin)

        parser = self._cache[origin]
        if parser is None:
            return False
        return parser.can_fetch(self.config.user_agent, url)

    def _load(self, origin: str) -> RobotFileParser | None:
        robots_url = f"{origin}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            response = self.client.get(robots_url, headers={"User-Agent": self.config.user_agent})
        except httpx.HTTPError:
            return None

        if response.status_code == 404 and self.config.allow_on_robots_404:
            parser.parse([])
            return parser
        if response.status_code in {401, 403} or response.status_code >= 500:
            return None
        if response.status_code >= 400:
            parser.parse([])
            return parser

        parser.parse(response.text.splitlines())
        return parser


class HostRateLimiter:
    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = max(delay_seconds, 0)
        self._last_request_at: dict[str, float] = {}

    def wait(self, url: str) -> None:
        host = urlparse(url).netloc
        now = time.monotonic()
        last = self._last_request_at.get(host)
        if last is not None:
            remaining = self.delay_seconds - (now - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at[host] = time.monotonic()


def normalize_url(url: str) -> str | None:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return urldefrag(parsed.geturl())[0]


def read_seed_urls(path: str) -> list[str]:
    urls: list[str] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            normalized = normalize_url(stripped)
            if normalized:
                urls.append(normalized)
    return urls


def _flatten_jsonld(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            found.extend(_flatten_jsonld(item))
        return found
    if not isinstance(value, dict):
        return found

    found.append(value)
    graph = value.get("@graph")
    if isinstance(graph, list):
        found.extend(_flatten_jsonld(graph))
    return found


def _is_jobposting(node: dict[str, Any]) -> bool:
    node_type = node.get("@type")
    if isinstance(node_type, str):
        return node_type.lower() == "jobposting"
    if isinstance(node_type, list):
        return any(str(item).lower() == "jobposting" for item in node_type)
    return False


def extract_jobposting_nodes(html: str) -> list[dict[str, Any]]:
    parser = JsonLdParser()
    parser.feed(html)
    jobs: list[dict[str, Any]] = []
    for block in parser.blocks:
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            continue
        for node in _flatten_jsonld(payload):
            if _is_jobposting(node):
                jobs.append(node)
    return jobs


def discover_job_links(base_url: str, html: str) -> list[str]:
    parser = LinkParser(base_url)
    parser.feed(html)
    base_host = urlparse(base_url).netloc
    discovered = []
    for link in sorted(parser.links):
        parsed = urlparse(link)
        if parsed.netloc != base_host:
            continue
        lower = parsed.path.lower()
        if any(hint in lower for hint in JOB_LINK_HINTS):
            discovered.append(link)
    return discovered


def _clean_html_text(value: Any) -> str:
    text = unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _string_value(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("name", "value", "text", "@id"):
            if value.get(key):
                return str(value[key]).strip()
        return ""
    if isinstance(value, list):
        parts = [_string_value(item) for item in value]
        return ", ".join(part for part in parts if part)
    return str(value or "").strip()


def _company(node: dict[str, Any]) -> str:
    value = node.get("hiringOrganization") or node.get("organization")
    if isinstance(value, dict):
        return _string_value(value.get("name") or value.get("legalName") or value.get("url")) or "Unknown"
    return _string_value(value) or "Unknown"


def _location(node: dict[str, Any]) -> str:
    if str(node.get("jobLocationType") or "").upper() == "TELECOMMUTE":
        return "Remote"

    value = node.get("jobLocation") or node.get("applicantLocationRequirements")
    if isinstance(value, list):
        return _string_value([_location({"jobLocation": item}) for item in value])
    if isinstance(value, dict):
        address = value.get("address")
        if isinstance(address, dict):
            parts = [
                address.get("addressLocality"),
                address.get("addressRegion"),
                address.get("addressCountry"),
            ]
            text = ", ".join(str(part) for part in parts if part)
            if text:
                return text
        return _string_value(value.get("name") or address or value)
    return _string_value(value) or "Unknown"


def _salary(node: dict[str, Any]) -> tuple[int | None, int | None, str | None]:
    base_salary = node.get("baseSalary")
    if not isinstance(base_salary, dict):
        return None, None, None

    currency = str(base_salary.get("currency") or "").upper()
    if currency and currency != "AUD":
        return None, None, None

    value = base_salary.get("value")
    if not isinstance(value, dict):
        return None, None, None

    def parse(raw: Any) -> int | None:
        if raw in (None, ""):
            return None
        try:
            return int(float(str(raw).replace(",", "")))
        except ValueError:
            return None

    salary_min = parse(value.get("minValue") or value.get("value"))
    salary_max = parse(value.get("maxValue") or value.get("value"))
    unit = str(value.get("unitText") or "YEAR").lower()
    period = {
        "year": "annual",
        "yearly": "annual",
        "month": "monthly",
        "week": "weekly",
        "day": "daily",
        "hour": "hourly",
    }.get(unit, "annual")
    return salary_min, salary_max, period


def map_jobposting_node(node: dict[str, Any], source_url: str) -> dict[str, object] | None:
    title = _string_value(node.get("title"))
    description = _clean_html_text(node.get("description"))
    listed_at = _string_value(node.get("datePosted") or node.get("dateCreated"))
    if not title or not description or not listed_at:
        return None

    identifier = node.get("identifier")
    if isinstance(identifier, dict):
        external_id = _string_value(identifier.get("value") or identifier.get("@id"))
    else:
        external_id = _string_value(identifier)
    if not external_id:
        external_id = sha256(f"{source_url}|{title}|{listed_at}".encode("utf-8")).hexdigest()[:24]

    salary_min, salary_max, salary_period = _salary(node)
    work_mode = "remote" if str(node.get("jobLocationType") or "").upper() == "TELECOMMUTE" else None
    work_type = _string_value(node.get("employmentType")) or None

    row: dict[str, object] = {
        "source": f"crawler:{urlparse(source_url).netloc}",
        "external_id": external_id,
        "title": title,
        "company": _company(node),
        "location": _location(node),
        "description": description,
        "listed_at": listed_at,
        "source_url": source_url,
        "work_mode": work_mode,
        "work_type": work_type,
        "role_hint": title,
    }
    if salary_min is not None:
        row["salary_min"] = salary_min
    if salary_max is not None:
        row["salary_max"] = salary_max
    if salary_period:
        row["salary_period"] = salary_period
    return row


class StructuredJobCrawler:
    def __init__(self, config: CrawlConfig | None = None) -> None:
        self.config = config or CrawlConfig()

    def crawl(self, seed_urls: list[str]) -> CrawlResult:
        normalized_seeds = [url for url in (normalize_url(url) for url in seed_urls) if url]
        queue: deque[tuple[str, int]] = deque((url, 0) for url in normalized_seeds)
        seen: set[str] = set()
        visited: list[str] = []
        skipped: list[str] = []
        rows: list[dict[str, object]] = []

        limiter = HostRateLimiter(self.config.request_delay_seconds)
        with httpx.Client(
            timeout=self.config.timeout_seconds,
            follow_redirects=True,
            verify=self.config.verify_tls,
        ) as client:
            robots = RobotsPolicy(client, self.config)
            while queue and len(visited) < self.config.max_urls:
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
                if response.status_code >= 400 or "text/html" not in content_type:
                    skipped.append(normalized)
                    continue

                html = response.text
                visited.append(str(response.url))
                for node in extract_jobposting_nodes(html):
                    row = map_jobposting_node(node, str(response.url))
                    if row is not None:
                        rows.append(row)

                if depth < self.config.discover_depth:
                    for link in discover_job_links(str(response.url), html):
                        if link not in seen and len(seen) + len(queue) < self.config.max_urls:
                            queue.append((link, depth + 1))

        return CrawlResult(
            visited_urls=visited,
            skipped_urls=skipped,
            fetched_pages=len(visited),
            extracted_rows=rows,
        )
