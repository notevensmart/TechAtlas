import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, BarChart3, BookOpen, Database, GitBranch, ShieldCheck, Table2 } from "lucide-react";
import { api } from "./api/client";
import { BreakdownList } from "./components/BreakdownList";
import { CoOccurrencePanel } from "./components/CoOccurrencePanel";
import { EmptyState } from "./components/EmptyState";
import { FilterBar } from "./components/FilterBar";
import { ListingsTable } from "./components/ListingsTable";
import { MarketSignalsView, type SignalsAudience } from "./components/MarketSignalsView";
import { Methodology } from "./components/Methodology";
import { MetricCard } from "./components/MetricCard";
import { SkillDemandChart } from "./components/SkillDemandChart";
import { SourceHealthView } from "./components/SourceHealthView";
import { TrendChart } from "./components/TrendChart";
import { useFilters } from "./hooks/useFilters";
import { formatDate, formatNumber } from "./utils/format";

type Tab = "overview" | "signals" | "skills" | "relationships" | "listings" | "coverage" | "methodology";

const tabs: { id: Tab; label: string; icon: typeof BarChart3 }[] = [
  { id: "overview", label: "Overview", icon: BarChart3 },
  { id: "signals", label: "Signals", icon: Activity },
  { id: "skills", label: "Skills", icon: Database },
  { id: "relationships", label: "Relationships", icon: GitBranch },
  { id: "listings", label: "Listings", icon: Table2 },
  { id: "coverage", label: "Coverage", icon: ShieldCheck },
  { id: "methodology", label: "Methodology", icon: BookOpen }
];

export default function App() {
  const { filters, setFilter, resetFilters } = useFilters();
  const [tab, setTab] = useState<Tab>("overview");
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [signalsAudience, setSignalsAudience] = useState<SignalsAudience>("recruiter");
  const thirtyDayFilters = useMemo(() => ({ ...filters, days: "30" as const }), [filters]);

  const summary = useQuery({ queryKey: ["summary", filters], queryFn: () => api.summary(filters) });
  const imports = useQuery({ queryKey: ["imports"], queryFn: api.importSummary });
  const demand = useQuery({ queryKey: ["demand", filters], queryFn: () => api.demand(filters) });
  const breakdowns = useQuery({ queryKey: ["breakdowns", filters], queryFn: () => api.breakdowns(filters) });
  const coOccurrence = useQuery({ queryKey: ["cooccurrence", filters], queryFn: () => api.coOccurrence(filters) });
  const sourceHealth = useQuery({
    queryKey: ["source-health", filters],
    queryFn: () => api.sourceHealth(filters),
    enabled: tab === "coverage"
  });
  const sourceHealth30d = useQuery({
    queryKey: ["source-health", thirtyDayFilters],
    queryFn: () => api.sourceHealth(thirtyDayFilters),
    enabled: tab === "coverage"
  });
  const signalSummary = useQuery({
    queryKey: ["market-signals-summary", filters],
    queryFn: () => api.signalSummary(filters),
    enabled: tab === "signals"
  });
  const signalPathways = useQuery({
    queryKey: ["market-signals-pathways", filters],
    queryFn: () => api.signalPathways(filters),
    enabled: tab === "signals" && signalsAudience === "candidate"
  });
  const listings = useQuery({
    queryKey: ["listings", filters, page, search],
    queryFn: () => api.listings(filters, page, search)
  });

  const activeSkill = selectedSkill ?? demand.data?.[0]?.skill ?? null;
  const history = useQuery({
    queryKey: ["history", activeSkill, filters.days],
    queryFn: () => api.history(activeSkill!, filters.days),
    enabled: Boolean(activeSkill)
  });

  useEffect(() => {
    setPage(1);
  }, [filters, search]);

  useEffect(() => {
    if (!selectedSkill && demand.data?.[0]?.skill) {
      setSelectedSkill(demand.data[0].skill);
    }
  }, [demand.data, selectedSkill]);

  const hasNoData = (summary.data?.total_postings ?? 0) === 0;
  const metricCards = useMemo(
    () => [
      { label: "Postings", value: formatNumber(summary.data?.total_postings ?? 0), accent: "sky" as const },
      { label: "Latest import", value: formatDate(summary.data?.latest_import_at), accent: "teal" as const },
      { label: "Skills detected", value: formatNumber(summary.data?.skills_detected ?? 0), accent: "amber" as const },
      { label: "Top growing skill", value: summary.data?.top_growing_skill ?? "n/a", accent: "violet" as const },
      { label: "Top city", value: summary.data?.top_city ?? "n/a", accent: "rose" as const },
      { label: "Salary coverage", value: `${summary.data?.salary_coverage_pct ?? 0}%`, accent: "slate" as const }
    ],
    [summary.data]
  );

  return (
    <div className="min-h-screen bg-surface text-ink">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <div>
            <h1 className="text-xl font-semibold tracking-normal text-ink">TechAtlas</h1>
            <p className="text-sm text-slate-600">Australian Tech Job Market Intelligence</p>
          </div>
          <div className="rounded border border-line px-3 py-2 text-sm text-slate-700">
            <span className="font-medium">Data:</span>{" "}
            {imports.data?.latest_status ? `${imports.data.latest_status}, ${formatDate(imports.data.latest_import_at)}` : "no imports yet"}
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-4 px-4 py-5 sm:px-6 lg:px-8">
        <FilterBar filters={filters} onChange={setFilter} onReset={resetFilters} />

        <nav className="flex gap-2 overflow-x-auto border-b border-line" aria-label="Dashboard sections">
          {tabs.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                type="button"
                className={`focus-ring inline-flex items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium ${
                  tab === item.id
                    ? "border-sky-600 text-sky-700"
                    : "border-transparent text-slate-600 hover:text-ink"
                }`}
                onClick={() => setTab(item.id)}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </button>
            );
          })}
        </nav>

        {summary.isError ? (
          <EmptyState title="API unavailable" message="Start the FastAPI backend and confirm VITE_API_BASE_URL points to it." />
        ) : null}

        {tab === "overview" ? (
          <div className="grid gap-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              {metricCards.map((card) => (
                <MetricCard key={card.label} label={card.label} value={card.value} accent={card.accent} />
              ))}
            </div>
            {hasNoData ? (
              <EmptyState
                title="No real job data imported"
                message="Run the CLI importer with a permitted CSV or JSONL export to populate the dashboard."
              />
            ) : (
              <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
                <SkillDemandChart data={demand.data ?? []} onSelectSkill={setSelectedSkill} />
                <div className="grid gap-4">
                  <BreakdownList title="Cities" items={breakdowns.data?.cities ?? []} />
                  <BreakdownList title="Role Families" items={breakdowns.data?.role_families ?? []} />
                </div>
              </div>
            )}
          </div>
        ) : null}

        {tab === "skills" ? (
          <div className="grid gap-4 lg:grid-cols-[1.25fr_1fr]">
            <SkillDemandChart data={demand.data ?? []} onSelectSkill={setSelectedSkill} />
            <TrendChart skill={activeSkill} data={history.data ?? []} />
          </div>
        ) : null}

        {tab === "signals" ? (
          <MarketSignalsView
            audience={signalsAudience}
            onAudienceChange={setSignalsAudience}
            summary={signalSummary.data}
            pathways={signalPathways.data}
            isLoading={signalSummary.isLoading || signalPathways.isLoading}
            isError={signalSummary.isError || signalPathways.isError}
          />
        ) : null}

        {tab === "relationships" ? (
          <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
            <CoOccurrencePanel items={coOccurrence.data ?? []} />
            <div className="grid gap-4">
              <BreakdownList title="Work Modes" items={breakdowns.data?.work_modes ?? []} />
              <BreakdownList title="Experience Levels" items={breakdowns.data?.experience_levels ?? []} />
            </div>
          </div>
        ) : null}

        {tab === "listings" ? (
          <ListingsTable data={listings.data} search={search} onSearch={setSearch} page={page} onPage={setPage} />
        ) : null}

        {tab === "coverage" ? (
          <SourceHealthView
            data={sourceHealth.data}
            thirtyDayData={sourceHealth30d.data}
            isLoading={sourceHealth.isLoading}
            isError={sourceHealth.isError}
          />
        ) : null}

        {tab === "methodology" ? <Methodology /> : null}
      </main>
    </div>
  );
}
