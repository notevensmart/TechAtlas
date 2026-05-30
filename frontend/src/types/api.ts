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

