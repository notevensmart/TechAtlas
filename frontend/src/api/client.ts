import type {
  BreakdownsResponse,
  CoOccurrenceItem,
  Filters,
  ImportSummary,
  ListingsResponse,
  MarketNote,
  MarketSignalsSummary,
  MomentumSignal,
  RoleArchetypeSignal,
  SkillClusterSignal,
  SkillDemandItem,
  SkillHistoryPoint,
  SkillPathwaySignal,
  SourceHealthItem,
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
  sourceHealth: (filters: Filters) => get<SourceHealthItem[]>("/api/v1/sources/health", { ...filters }),
  signalSummary: (filters: Filters) => get<MarketSignalsSummary>("/api/v1/market/signals/summary", { ...filters }),
  signalClusters: (filters: Filters) => get<SkillClusterSignal[]>("/api/v1/market/signals/clusters", { ...filters }),
  signalArchetypes: (filters: Filters) =>
    get<RoleArchetypeSignal[]>("/api/v1/market/signals/archetypes", { ...filters }),
  signalMomentum: (filters: Filters) => get<MomentumSignal[]>("/api/v1/market/signals/momentum", { ...filters }),
  signalPathways: (filters: Filters) => get<SkillPathwaySignal[]>("/api/v1/market/signals/pathways", { ...filters }),
  signalNotes: (filters: Filters) => get<MarketNote[]>("/api/v1/market/signals/notes", { ...filters }),
  coOccurrence: (filters: Filters) =>
    get<CoOccurrenceItem[]>("/api/v1/skills/co-occurrence", { ...filters, limit: 30 }),
  listings: (filters: Filters, page: number, search: string) =>
    get<ListingsResponse>("/api/v1/listings", { ...filters, page, page_size: 25, search })
};
