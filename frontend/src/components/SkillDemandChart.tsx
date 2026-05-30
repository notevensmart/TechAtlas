import type { SkillDemandItem } from "../types/api";
import { EmptyState } from "./EmptyState";

interface SkillDemandChartProps {
  data: SkillDemandItem[];
  onSelectSkill: (skill: string) => void;
}

export function SkillDemandChart({ data, onSelectSkill }: SkillDemandChartProps) {
  if (!data.length) {
    return (
      <EmptyState
        title="No skill demand yet"
        message="Import permitted real job data to populate skill demand rankings."
      />
    );
  }

  const maxCount = Math.max(...data.map((item) => item.listing_count), 1);

  return (
    <div className="h-[420px] rounded border border-line bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Skill Demand</h2>
          <p className="text-sm text-slate-600">Postings mentioning each skill in the selected period.</p>
        </div>
      </div>
      <div className="h-[340px] overflow-y-auto pr-1">
        <div className="grid gap-2">
          {data.map((item) => {
            const width = `${Math.max((item.listing_count / maxCount) * 100, 3)}%`;

            return (
              <button
                key={item.skill}
                type="button"
                className="focus-ring grid min-h-8 grid-cols-[minmax(8.5rem,11rem)_minmax(0,1fr)_3.5rem] items-center gap-3 rounded px-2 py-1 text-left hover:bg-slate-50"
                onClick={() => onSelectSkill(item.skill)}
                title={`${item.skill}: ${item.listing_count} postings`}
              >
                <span className="truncate whitespace-nowrap text-sm font-medium text-slate-700">
                  {item.skill}
                </span>
                <span className="h-3 min-w-0 overflow-hidden rounded bg-slate-100">
                  <span
                    className="block h-full rounded bg-teal-700"
                    style={{ width }}
                    aria-hidden="true"
                  />
                </span>
                <span className="whitespace-nowrap text-right text-sm tabular-nums text-slate-600">
                  {item.listing_count}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
