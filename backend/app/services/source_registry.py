from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_SOURCES_PATH = ROOT_DIR / "ingestion" / "sources.yml"


@dataclass(frozen=True)
class SourceFilters:
    country: str | None = "AU"
    tech_only: bool = True
    include_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SourceDefinition:
    key: str
    adapter: str
    seeds: list[str]
    enabled: bool = True
    max_urls: int | None = None
    discover_depth: int = 1
    filters: SourceFilters = field(default_factory=SourceFilters)
    compliance_note: str | None = None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    raise ValueError("expected a string or list of strings")


def _source_from_mapping(raw: dict[str, Any]) -> SourceDefinition:
    filters = raw.get("filters") or {}
    if not isinstance(filters, dict):
        raise ValueError("source filters must be a mapping")

    return SourceDefinition(
        key=str(raw["key"]).strip(),
        adapter=str(raw["adapter"]).strip(),
        seeds=_string_list(raw.get("seeds")),
        enabled=bool(raw.get("enabled", True)),
        max_urls=int(raw["max_urls"]) if raw.get("max_urls") is not None else None,
        discover_depth=int(raw.get("discover_depth", 1)),
        filters=SourceFilters(
            country=str(filters["country"]).upper() if filters.get("country") else None,
            tech_only=bool(filters.get("tech_only", True)),
            include_keywords=_string_list(filters.get("include_keywords")),
            exclude_keywords=_string_list(filters.get("exclude_keywords")),
        ),
        compliance_note=str(raw.get("compliance_note") or "").strip() or None,
    )


def load_source_registry(path: Path | None = None) -> list[SourceDefinition]:
    registry_path = path or DEFAULT_SOURCES_PATH
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    sources = payload.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("source registry must contain a top-level 'sources' list")

    loaded = []
    seen: set[str] = set()
    for raw in sources:
        if not isinstance(raw, dict):
            raise ValueError("each source registry entry must be a mapping")
        source = _source_from_mapping(raw)
        if not source.key:
            raise ValueError("source key cannot be blank")
        if source.key in seen:
            raise ValueError(f"duplicate source key: {source.key}")
        if not source.seeds:
            raise ValueError(f"source {source.key} must define at least one seed")
        seen.add(source.key)
        loaded.append(source)
    return loaded
