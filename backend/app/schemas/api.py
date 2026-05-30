from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ImportSummary(BaseModel):
    latest_import_at: datetime | None
    latest_status: str | None
    total_imports: int
    rows_seen: int
    rows_imported: int
    rows_rejected: int


class SummaryStats(BaseModel):
    total_postings: int
    latest_import_at: datetime | None
    skills_detected: int
    top_growing_skill: str | None
    top_city: str | None
    salary_coverage_pct: float


class SkillDemandItem(BaseModel):
    skill: str
    category: str
    listing_count: int
    share_of_postings_pct: float
    delta_count: int | None = None
    delta_pct: float | None = None
    salary_listing_count: int
    avg_salary: int | None = None
    median_salary: int | None = None


class SkillHistoryPoint(BaseModel):
    date: date
    listing_count: int
    share_of_postings_pct: float


class BreakdownItem(BaseModel):
    name: str
    count: int
    pct: float


class BreakdownsResponse(BaseModel):
    cities: list[BreakdownItem]
    role_families: list[BreakdownItem]
    work_modes: list[BreakdownItem]
    experience_levels: list[BreakdownItem]


class CoOccurrenceItem(BaseModel):
    skill_a: str
    skill_b: str
    count: int
    strength_score: float


class ListingItem(BaseModel):
    id: int
    source: str
    external_id: str
    source_url: str | None
    title: str
    company: str
    raw_location: str
    city: str
    listed_at: datetime
    salary_min_annual: int | None
    salary_max_annual: int | None
    salary_mid_annual: int | None
    work_mode: str
    work_type: str | None
    experience_level: str
    role_family: str
    skills: list[str]
    description_snippet: str

    model_config = ConfigDict(from_attributes=True)


class ListingsResponse(BaseModel):
    items: list[ListingItem]
    page: int
    page_size: int
    total: int
    total_pages: int

