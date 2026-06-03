export type RangeValue = "30" | "90" | "180" | "all";

export interface Filters {
  days: RangeValue;
  city?: string;
  role_family?: string;
  skill_category?: string;
  experience_level?: string;
  work_mode?: string;
}

export interface ImportSummary {
  latest_import_at: string | null;
  latest_status: string | null;
  total_imports: number;
  rows_seen: number;
  rows_imported: number;
  rows_rejected: number;
}

export interface SummaryStats {
  total_postings: number;
  latest_import_at: string | null;
  skills_detected: number;
  top_growing_skill: string | null;
  top_city: string | null;
  salary_coverage_pct: number;
}

export interface SkillDemandItem {
  skill: string;
  category: string;
  listing_count: number;
  share_of_postings_pct: number;
  delta_count: number | null;
  delta_pct: number | null;
  salary_listing_count: number;
  avg_salary: number | null;
  median_salary: number | null;
}

export interface SkillHistoryPoint {
  date: string;
  listing_count: number;
  share_of_postings_pct: number;
}

export interface BreakdownItem {
  name: string;
  count: number;
  pct: number;
}

export interface BreakdownsResponse {
  cities: BreakdownItem[];
  role_families: BreakdownItem[];
  work_modes: BreakdownItem[];
  experience_levels: BreakdownItem[];
}

export interface CoOccurrenceItem {
  skill_a: string;
  skill_b: string;
  count: number;
  strength_score: number;
}

export interface SourceHealthItem {
  source: string;
  adapter: string | null;
  latest_status: string | null;
  latest_crawl_finished_at: string | null;
  pages_fetched: number;
  pages_skipped: number;
  rows_extracted: number;
  rows_imported: number;
  total_listings: number;
  period_listings: number;
  latest_listing_listed_at: string | null;
  first_listing_listed_at: string | null;
  quality_tier: "high" | "medium" | "low" | string;
  notes: string | null;
}

export interface MomentumSignal {
  name: string;
  signal_type: string;
  current_count: number;
  previous_count: number;
  delta_count: number;
  delta_pct: number | null;
  momentum: "rising" | "stable" | "falling" | "new" | string;
}

export interface RecruiterDifficultySignal {
  name: string;
  signal_type: string;
  difficulty_score: number;
  difficulty_label: "low" | "moderate" | "high" | "very high" | string;
  reasons: string[];
  senior_share_pct: number;
  average_required_skills: number;
  salary_confidence_pct: number;
}

export interface CandidateOpportunitySignal {
  name: string;
  signal_type: string;
  opportunity_score: number;
  opportunity_label: "accessible" | "competitive" | "advanced" | "niche" | string;
  reasons: string[];
  demand_count: number;
  entry_mid_share_pct: number;
  senior_share_pct: number;
  adjacent_skill_count: number;
}

export interface SkillClusterSignal {
  name: string;
  skills: string[];
  listing_count: number;
  share_of_postings_pct: number;
  demand_concentration_pct: number;
  top_city: string | null;
  top_skills: string[];
  senior_share_pct: number;
  average_skills_per_listing: number;
  momentum: MomentumSignal;
  recruiter_difficulty: RecruiterDifficultySignal;
  candidate_opportunity: CandidateOpportunitySignal;
}

export interface RoleArchetypeSignal {
  name: string;
  listing_count: number;
  share_of_postings_pct: number;
  top_skills: string[];
  top_clusters: string[];
  top_city: string | null;
  senior_share_pct: number;
  average_skills_per_listing: number;
  momentum: MomentumSignal;
  recruiter_difficulty: RecruiterDifficultySignal;
  candidate_opportunity: CandidateOpportunitySignal;
}

export interface SkillPathwaySignal {
  archetype: string;
  primary_cluster: string | null;
  demand_count: number;
  core_skills: string[];
  common_adjacent_skills: string[];
  stretch_skills: string[];
  related_archetypes: string[];
  opportunity: CandidateOpportunitySignal;
}

export interface MarketNote {
  audience: "recruiter" | "candidate" | string;
  subject: string;
  signal_type: string;
  note: string;
}

export interface MarketSignalsSummary {
  total_postings: number;
  period_days: RangeValue | string;
  top_clusters: SkillClusterSignal[];
  top_archetypes: RoleArchetypeSignal[];
  momentum: MomentumSignal[];
  recruiter_difficulty: RecruiterDifficultySignal;
  candidate_opportunities: CandidateOpportunitySignal[];
  notes: MarketNote[];
}

export interface ListingItem {
  id: number;
  source: string;
  external_id: string;
  source_url: string | null;
  title: string;
  company: string;
  raw_location: string;
  city: string;
  listed_at: string;
  salary_min_annual: number | null;
  salary_max_annual: number | null;
  salary_mid_annual: number | null;
  work_mode: string;
  work_type: string | null;
  experience_level: string;
  role_family: string;
  skills: string[];
  description_snippet: string;
}

export interface ListingsResponse {
  items: ListingItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}
