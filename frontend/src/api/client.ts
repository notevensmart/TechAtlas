import type {
  BreakdownsResponse,
  CoOccurrenceItem,
  Filters,
  ImportSummary,
  ListingsResponse,
  SkillDemandItem,
  SkillHistoryPoint,
  SummaryStats
} from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type QueryParams = Record<string, string | number | undefined | null>;

function buildQuery(params: QueryParams): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const text = query.toString();
  return text ? `?${text}` : "";
}

async function get<T>(path: string, params: Record<string, string | number | undefined | null> = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}${buildQuery(params)}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  importSummary: () => get<ImportSummary>("/api/v1/imports/summary"),
  summary: (filters: Filters) => get<SummaryStats>("/api/v1/stats/summary", { ...filters }),
  demand: (filters: Filters) => get<SkillDemandItem[]>("/api/v1/skills/demand", { ...filters, limit: 25 }),
  history: (skill: string, days: Filters["days"]) =>
    get<SkillHistoryPoint[]>("/api/v1/skills/history", { skill, days }),
  breakdowns: (filters: Filters) => get<BreakdownsResponse>("/api/v1/stats/breakdowns", { ...filters }),
  coOccurrence: (filters: Filters) =>
    get<CoOccurrenceItem[]>("/api/v1/skills/co-occurrence", { ...filters, limit: 30 }),
  listings: (filters: Filters, page: number, search: string) =>
    get<ListingsResponse>("/api/v1/listings", { ...filters, page, page_size: 25, search })
};
