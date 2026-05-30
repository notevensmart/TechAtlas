import { RotateCcw } from "lucide-react";
import type { Filters, RangeValue } from "../types/api";

interface FilterBarProps {
  filters: Filters;
  onChange: (key: keyof Filters, value: string | undefined) => void;
  onReset: () => void;
}

const cities = ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Canberra", "Remote", "Other"];
const roleFamilies = [
  "Software Engineering",
  "Frontend",
  "Backend",
  "Data Analytics",
  "Data Science",
  "DevOps",
  "Cloud",
  "AI/ML Engineering",
  "Other/Unknown"
];
const categories = ["language", "frontend", "backend", "cloud", "database", "devops", "data", "AI/ML", "testing", "tooling"];
const levels = ["grad", "junior", "mid", "senior", "unknown"];
const modes = ["remote", "hybrid", "onsite", "unknown"];
const ranges: { label: string; value: RangeValue }[] = [
  { label: "30d", value: "30" },
  { label: "90d", value: "90" },
  { label: "180d", value: "180" },
  { label: "All", value: "all" }
];

function SelectFilter({
  label,
  value,
  options,
  onChange
}: {
  label: string;
  value?: string;
  options: string[];
  onChange: (value: string | undefined) => void;
}) {
  return (
    <label className="grid gap-1 text-xs font-medium text-slate-600">
      {label}
      <select
        className="focus-ring h-9 rounded border border-line bg-white px-2 text-sm text-ink"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value || undefined)}
      >
        <option value="">All</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

export function FilterBar({ filters, onChange, onReset }: FilterBarProps) {
  return (
    <div className="rounded border border-line bg-white p-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="grid gap-1 text-xs font-medium text-slate-600">
          Date range
          <div className="flex h-9 overflow-hidden rounded border border-line bg-white">
            {ranges.map((range) => (
              <button
                key={range.value}
                className={`focus-ring min-w-14 px-3 text-sm ${
                  filters.days === range.value ? "bg-ink text-white" : "text-slate-700 hover:bg-slate-50"
                }`}
                type="button"
                onClick={() => onChange("days", range.value)}
              >
                {range.label}
              </button>
            ))}
          </div>
        </div>
        <SelectFilter label="City" value={filters.city} options={cities} onChange={(value) => onChange("city", value)} />
        <SelectFilter
          label="Role"
          value={filters.role_family}
          options={roleFamilies}
          onChange={(value) => onChange("role_family", value)}
        />
        <SelectFilter
          label="Skill category"
          value={filters.skill_category}
          options={categories}
          onChange={(value) => onChange("skill_category", value)}
        />
        <SelectFilter
          label="Level"
          value={filters.experience_level}
          options={levels}
          onChange={(value) => onChange("experience_level", value)}
        />
        <SelectFilter
          label="Work mode"
          value={filters.work_mode}
          options={modes}
          onChange={(value) => onChange("work_mode", value)}
        />
        <button
          type="button"
          className="focus-ring inline-flex h-9 items-center gap-2 rounded border border-line bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
          onClick={onReset}
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          Reset
        </button>
      </div>
    </div>
  );
}

