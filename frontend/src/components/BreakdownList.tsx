import type { BreakdownItem } from "../types/api";
import { EmptyState } from "./EmptyState";

interface BreakdownListProps {
  title: string;
  items: BreakdownItem[];
}

export function BreakdownList({ title, items }: BreakdownListProps) {
  if (!items.length) {
    return <EmptyState title={`No ${title.toLowerCase()} data`} message="Import real listings to populate this breakdown." />;
  }

  return (
    <div className="rounded border border-line bg-white p-4">
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      <div className="mt-4 grid gap-3">
        {items.slice(0, 8).map((item) => (
          <div key={item.name}>
            <div className="mb-1 flex items-center justify-between gap-3 text-sm">
              <span className="truncate font-medium text-slate-700">{item.name}</span>
              <span className="shrink-0 text-slate-500">{item.count} postings</span>
            </div>
            <div className="h-2 rounded bg-slate-100">
              <div className="h-2 rounded bg-amber-500" style={{ width: `${Math.min(item.pct, 100)}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

