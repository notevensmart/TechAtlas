import { Activity, Briefcase, GraduationCap, Minus, TrendingDown, TrendingUp } from "lucide-react";
import type {
  CandidateOpportunitySignal,
  MarketNote,
  MarketSignalsSummary,
  MomentumSignal,
  RecruiterDifficultySignal,
  RoleArchetypeSignal,
  SkillClusterSignal,
  SkillPathwaySignal
} from "../types/api";
import { formatNumber } from "../utils/format";
import { EmptyState } from "./EmptyState";

export type SignalsAudience = "recruiter" | "candidate";

interface MarketSignalsViewProps {
  audience: SignalsAudience;
  onAudienceChange: (audience: SignalsAudience) => void;
  summary: MarketSignalsSummary | undefined;
  pathways: SkillPathwaySignal[] | undefined;
  isLoading: boolean;
  isError: boolean;
}

function formatPct(value: number): string {
  return `${Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1)}%`;
}

function scoreTone(score: number): string {
  if (score >= 75) return "border-rose-200 bg-rose-50 text-rose-800";
  if (score >= 55) return "border-amber-200 bg-amber-50 text-amber-800";
  if (score >= 35) return "border-sky-200 bg-sky-50 text-sky-800";
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function opportunityTone(label: string): string {
  if (label === "accessible") return "border-teal-200 bg-teal-50 text-teal-800";
  if (label === "competitive") return "border-sky-200 bg-sky-50 text-sky-800";
  if (label === "advanced") return "border-amber-200 bg-amber-50 text-amber-800";
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function momentumTone(momentum: string): string {
  if (momentum === "rising" || momentum === "new") return "border-teal-200 bg-teal-50 text-teal-800";
  if (momentum === "falling") return "border-rose-200 bg-rose-50 text-rose-800";
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function MomentumIcon({ momentum }: { momentum: string }) {
  if (momentum === "rising" || momentum === "new") return <TrendingUp className="h-4 w-4" aria-hidden="true" />;
  if (momentum === "falling") return <TrendingDown className="h-4 w-4" aria-hidden="true" />;
  return <Minus className="h-4 w-4" aria-hidden="true" />;
}

function AudienceToggle({
  audience,
  onAudienceChange
}: {
  audience: SignalsAudience;
  onAudienceChange: (audience: SignalsAudience) => void;
}) {
  const options: { id: SignalsAudience; label: string; icon: typeof Briefcase }[] = [
    { id: "recruiter", label: "Recruiter", icon: Briefcase },
    { id: "candidate", label: "Candidate", icon: GraduationCap }
  ];

  return (
    <div className="inline-flex rounded border border-line bg-white p-1" aria-label="Signals audience">
      {options.map((option) => {
        const Icon = option.icon;
        return (
          <button
            key={option.id}
            type="button"
            className={`focus-ring inline-flex min-w-28 items-center justify-center gap-2 rounded px-3 py-2 text-sm font-medium ${
              audience === option.id ? "bg-sky-600 text-white" : "text-slate-600 hover:bg-slate-50 hover:text-ink"
            }`}
            onClick={() => onAudienceChange(option.id)}
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function ScoreBlock({ signal }: { signal: RecruiterDifficultySignal }) {
  return (
    <section className="rounded border border-line bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Hiring Difficulty</h2>
          <p className="text-sm text-slate-600">{signal.name}</p>
        </div>
        <span className={`rounded border px-3 py-2 text-sm font-semibold ${scoreTone(signal.difficulty_score)}`}>
          {signal.difficulty_score}/100 - {signal.difficulty_label}
        </span>
      </div>
      <dl className="mt-4 grid gap-3 sm:grid-cols-3">
        <div>
          <dt className="text-xs font-medium uppercase tracking-normal text-slate-500">Senior share</dt>
          <dd className="mt-1 text-lg font-semibold text-ink">{formatPct(signal.senior_share_pct)}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-normal text-slate-500">Avg skills</dt>
          <dd className="mt-1 text-lg font-semibold text-ink">{signal.average_required_skills}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-normal text-slate-500">Salary visible</dt>
          <dd className="mt-1 text-lg font-semibold text-ink">{formatPct(signal.salary_confidence_pct)}</dd>
        </div>
      </dl>
      <ul className="mt-4 grid gap-2 text-sm leading-6 text-slate-700">
        {signal.reasons.slice(0, 4).map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </section>
  );
}

function RecruiterArchetypes({ items }: { items: RoleArchetypeSignal[] }) {
  if (!items.length) {
    return <EmptyState title="No archetype signals" message="No role archetypes match the selected filters." />;
  }

  return (
    <section className="rounded border border-line bg-white p-4">
      <h2 className="text-base font-semibold text-ink">Top Archetypes</h2>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[620px] text-left text-sm">
          <thead className="border-b border-line text-xs uppercase tracking-normal text-slate-500">
            <tr>
              <th className="py-2 pr-3 font-medium">Archetype</th>
              <th className="py-2 pr-3 font-medium">Postings</th>
              <th className="py-2 pr-3 font-medium">Difficulty</th>
              <th className="py-2 pr-3 font-medium">Senior</th>
              <th className="py-2 font-medium">Top skills</th>
            </tr>
          </thead>
          <tbody>
            {items.slice(0, 6).map((item) => (
              <tr key={item.name} className="border-b border-line last:border-0">
                <td className="py-3 pr-3 font-medium text-ink">{item.name}</td>
                <td className="py-3 pr-3 tabular-nums text-slate-700">{formatNumber(item.listing_count)}</td>
                <td className="py-3 pr-3">
                  <span className={`rounded border px-2 py-1 text-xs font-semibold ${scoreTone(item.recruiter_difficulty.difficulty_score)}`}>
                    {item.recruiter_difficulty.difficulty_label}
                  </span>
                </td>
                <td className="py-3 pr-3 tabular-nums text-slate-700">{formatPct(item.senior_share_pct)}</td>
                <td className="py-3 text-slate-700">{item.top_skills.slice(0, 3).join(", ") || "n/a"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ClusterDemand({ items }: { items: SkillClusterSignal[] }) {
  if (!items.length) {
    return <EmptyState title="No cluster signals" message="No skill clusters match the selected filters." />;
  }

  const maxCount = Math.max(...items.map((item) => item.listing_count), 1);
  return (
    <section className="rounded border border-line bg-white p-4">
      <h2 className="text-base font-semibold text-ink">Skill Clusters by Demand</h2>
      <div className="mt-4 grid gap-3">
        {items.slice(0, 8).map((item) => {
          const width = `${Math.max((item.listing_count / maxCount) * 100, 4)}%`;
          return (
            <div key={item.name} className="grid gap-2">
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="font-medium text-ink">{item.name}</span>
                <span className="tabular-nums text-slate-600">
                  {formatNumber(item.listing_count)} - {formatPct(item.share_of_postings_pct)}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded bg-slate-100">
                <div className="h-full rounded bg-teal-700" style={{ width }} />
              </div>
              <div className="text-xs text-slate-600">
                {item.top_city ? `${item.top_city}, ${formatPct(item.demand_concentration_pct)} concentration` : "No city concentration"}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function MomentumList({ items }: { items: MomentumSignal[] }) {
  if (!items.length) {
    return <EmptyState title="No momentum signals" message="Momentum appears once current and previous periods can be compared." />;
  }

  return (
    <section className="rounded border border-line bg-white p-4">
      <h2 className="text-base font-semibold text-ink">Momentum</h2>
      <div className="mt-3 grid gap-2">
        {items.slice(0, 8).map((item) => (
          <div key={`${item.signal_type}-${item.name}`} className="flex flex-wrap items-center justify-between gap-2 border-b border-line py-2 last:border-0">
            <div>
              <div className="text-sm font-medium text-ink">{item.name}</div>
              <div className="text-xs text-slate-600">
                {item.current_count} now, {item.previous_count} previous
              </div>
            </div>
            <span className={`inline-flex items-center gap-1 rounded border px-2 py-1 text-xs font-semibold ${momentumTone(item.momentum)}`}>
              <MomentumIcon momentum={item.momentum} />
              {item.momentum}
              {item.delta_pct !== null ? ` ${formatPct(item.delta_pct)}` : ""}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function NotesPanel({ title, notes }: { title: string; notes: MarketNote[] }) {
  if (!notes.length) {
    return <EmptyState title="No notes yet" message="Notes appear once matching signals have enough structure." />;
  }

  return (
    <section className="rounded border border-line bg-white p-4">
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      <div className="mt-3 grid gap-3">
        {notes.map((note) => (
          <div key={`${note.audience}-${note.signal_type}-${note.subject}-${note.note}`} className="border-b border-line pb-3 last:border-0 last:pb-0">
            <div className="text-xs font-medium uppercase tracking-normal text-slate-500">{note.subject}</div>
            <p className="mt-1 text-sm leading-6 text-slate-700">{note.note}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function OpportunityList({ items }: { items: CandidateOpportunitySignal[] }) {
  if (!items.length) {
    return <EmptyState title="No opportunity scores" message="No candidate opportunity segments match the selected filters." />;
  }

  return (
    <section className="rounded border border-line bg-white p-4">
      <h2 className="text-base font-semibold text-ink">Opportunity Scores</h2>
      <div className="mt-3 grid gap-3">
        {items.slice(0, 8).map((item) => (
          <div key={`${item.signal_type}-${item.name}`} className="border-b border-line pb-3 last:border-0 last:pb-0">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-sm font-medium text-ink">{item.name}</div>
                <div className="text-xs text-slate-600">
                  {formatNumber(item.demand_count)} postings - {formatPct(item.entry_mid_share_pct)} entry/mid
                </div>
              </div>
              <span className={`rounded border px-2 py-1 text-xs font-semibold ${opportunityTone(item.opportunity_label)}`}>
                {item.opportunity_score}/100 - {item.opportunity_label}
              </span>
            </div>
            {item.reasons[0] ? <p className="mt-2 text-sm leading-6 text-slate-700">{item.reasons[0]}</p> : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function SkillChips({ skills }: { skills: string[] }) {
  if (!skills.length) return <span className="text-sm text-slate-500">n/a</span>;
  return (
    <div className="flex flex-wrap gap-2">
      {skills.map((skill) => (
        <span key={skill} className="rounded border border-line bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700">
          {skill}
        </span>
      ))}
    </div>
  );
}

function PathwaysPanel({ pathways }: { pathways: SkillPathwaySignal[] }) {
  const visible = pathways.filter((item) => item.demand_count > 0).slice(0, 6);
  if (!visible.length) {
    return <EmptyState title="No role pathways" message="No inferred pathways match the selected filters." />;
  }

  return (
    <section className="rounded border border-line bg-white p-4">
      <h2 className="text-base font-semibold text-ink">Role Pathways</h2>
      <div className="mt-3 grid gap-4">
        {visible.map((item) => (
          <article key={item.archetype} className="border-b border-line pb-4 last:border-0 last:pb-0">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold text-ink">{item.archetype}</h3>
                <p className="text-xs text-slate-600">
                  {item.primary_cluster ?? "Unclear cluster"} - {formatNumber(item.demand_count)} postings
                </p>
              </div>
              <span className={`rounded border px-2 py-1 text-xs font-semibold ${opportunityTone(item.opportunity.opportunity_label)}`}>
                {item.opportunity.opportunity_label}
              </span>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <div>
                <div className="mb-2 text-xs font-medium uppercase tracking-normal text-slate-500">Core</div>
                <SkillChips skills={item.core_skills} />
              </div>
              <div>
                <div className="mb-2 text-xs font-medium uppercase tracking-normal text-slate-500">Adjacent</div>
                <SkillChips skills={item.common_adjacent_skills} />
              </div>
              <div>
                <div className="mb-2 text-xs font-medium uppercase tracking-normal text-slate-500">Stretch</div>
                <SkillChips skills={item.stretch_skills} />
              </div>
            </div>
            {item.related_archetypes.length ? (
              <p className="mt-3 text-sm text-slate-700">Related: {item.related_archetypes.join(", ")}</p>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function RecruiterSignals({ summary }: { summary: MarketSignalsSummary }) {
  const recruiterNotes = summary.notes.filter((note) => note.audience === "recruiter");
  return (
    <div className="grid gap-4">
      <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <ScoreBlock signal={summary.recruiter_difficulty} />
        <RecruiterArchetypes items={summary.top_archetypes} />
      </div>
      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <ClusterDemand items={summary.top_clusters} />
        <MomentumList items={summary.momentum} />
      </div>
      <NotesPanel title="Recruiter Market Notes" notes={recruiterNotes} />
    </div>
  );
}

function CandidateSignals({
  summary,
  pathways
}: {
  summary: MarketSignalsSummary;
  pathways: SkillPathwaySignal[] | undefined;
}) {
  const candidateNotes = summary.notes.filter((note) => note.audience === "candidate");
  return (
    <div className="grid gap-4">
      <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <OpportunityList items={summary.candidate_opportunities} />
        <PathwaysPanel pathways={pathways ?? []} />
      </div>
      <NotesPanel title="Candidate Market Notes" notes={candidateNotes} />
    </div>
  );
}

export function MarketSignalsView({
  audience,
  onAudienceChange,
  summary,
  pathways,
  isLoading,
  isError
}: MarketSignalsViewProps) {
  if (isError) {
    return <EmptyState title="Signals unavailable" message="Start the API backend and retry the selected filters." />;
  }

  if (isLoading && !summary) {
    return <EmptyState title="Loading signals" message="Market signal calculations are running for the selected filters." />;
  }

  if (!summary || summary.total_postings === 0) {
    return <EmptyState title="No market signals yet" message="Import or crawl matching job postings to populate this view." />;
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm text-slate-700">
          <Activity className="h-4 w-4 text-sky-700" aria-hidden="true" />
          <span>{formatNumber(summary.total_postings)} postings in scope</span>
        </div>
        <AudienceToggle audience={audience} onAudienceChange={onAudienceChange} />
      </div>
      {audience === "recruiter" ? (
        <RecruiterSignals summary={summary} />
      ) : (
        <CandidateSignals summary={summary} pathways={pathways} />
      )}
    </div>
  );
}
