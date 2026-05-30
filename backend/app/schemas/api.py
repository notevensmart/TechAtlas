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


class SourceHealthItem(BaseModel):
    source: str
    adapter: str | None
    latest_status: str | None
    latest_crawl_finished_at: datetime | None
    pages_fetched: int
    pages_skipped: int
    rows_extracted: int
    rows_imported: int
    total_listings: int
    period_listings: int
    latest_listing_listed_at: datetime | None
    first_listing_listed_at: datetime | None
    quality_tier: str
    notes: str | None


class MomentumSignal(BaseModel):
    name: str
    signal_type: str
    current_count: int
    previous_count: int
    delta_count: int
    delta_pct: float | None
    momentum: str


class RecruiterDifficultySignal(BaseModel):
    name: str
    signal_type: str
    difficulty_score: int
    difficulty_label: str
    reasons: list[str]
    senior_share_pct: float
    average_required_skills: float
    salary_confidence_pct: float


class CandidateOpportunitySignal(BaseModel):
    name: str
    signal_type: str
    opportunity_score: int
    opportunity_label: str
    reasons: list[str]
    demand_count: int
    entry_mid_share_pct: float
    senior_share_pct: float
    adjacent_skill_count: int


class SkillClusterSignal(BaseModel):
    name: str
    skills: list[str]
    listing_count: int
    share_of_postings_pct: float
    demand_concentration_pct: float
    top_city: str | None
    top_skills: list[str]
    senior_share_pct: float
    average_skills_per_listing: float
    momentum: MomentumSignal
    recruiter_difficulty: RecruiterDifficultySignal
    candidate_opportunity: CandidateOpportunitySignal


class RoleArchetypeSignal(BaseModel):
    name: str
    listing_count: int
    share_of_postings_pct: float
    top_skills: list[str]
    top_clusters: list[str]
    top_city: str | None
    senior_share_pct: float
    average_skills_per_listing: float
    momentum: MomentumSignal
    recruiter_difficulty: RecruiterDifficultySignal
    candidate_opportunity: CandidateOpportunitySignal


class SkillPathwaySignal(BaseModel):
    archetype: str
    primary_cluster: str | None
    demand_count: int
    core_skills: list[str]
    common_adjacent_skills: list[str]
    stretch_skills: list[str]
    related_archetypes: list[str]
    opportunity: CandidateOpportunitySignal


class MarketNote(BaseModel):
    audience: str
    subject: str
    signal_type: str
    note: str


class MarketSignalsSummary(BaseModel):
    total_postings: int
    period_days: str
    top_clusters: list[SkillClusterSignal]
    top_archetypes: list[RoleArchetypeSignal]
    momentum: list[MomentumSignal]
    recruiter_difficulty: RecruiterDifficultySignal
    candidate_opportunities: list[CandidateOpportunitySignal]
    notes: list[MarketNote]


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
