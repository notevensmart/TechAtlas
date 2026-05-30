import type { CoOccurrenceItem } from "../types/api";
import { EmptyState } from "./EmptyState";

export function CoOccurrencePanel({ items }: { items: CoOccurrenceItem[] }) {
  if (!items.length) {
    return (
      <EmptyState
        title="No skill relationships yet"
        message="Co-occurrence appears once imported listings contain multiple detected skills."
      />
    );
  }

  return (
    <div className="rounded border border-line bg-white p-4">
      <h2 className="text-base font-semibold text-ink">Skill Relationships</h2>
      <p className="text-sm text-slate-600">Ranked skill pairs found in the same postings.</p>
      <div className="mt-4 grid gap-2">
        {items.map((item) => (
          <div
            key={`${item.skill_a}-${item.skill_b}`}
            className="flex flex-wrap items-center justify-between gap-2 rounded border border-line px-3 py-2"
          >
            <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm font-medium text-ink">
              <span>{item.skill_a}</span>
              <span className="text-slate-400">+</span>
              <span>{item.skill_b}</span>
            </div>
            <span className="rounded bg-teal-50 px-2 py-1 text-xs font-semibold text-teal-800">
              {item.count} postings
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

