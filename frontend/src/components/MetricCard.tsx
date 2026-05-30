interface MetricCardProps {
  label: string;
  value: string;
  accent: "sky" | "teal" | "amber" | "rose" | "violet" | "slate";
}

const accentClasses = {
  sky: "border-sky-200 bg-sky-50 text-sky-800",
  teal: "border-teal-200 bg-teal-50 text-teal-800",
  amber: "border-amber-200 bg-amber-50 text-amber-800",
  rose: "border-rose-200 bg-rose-50 text-rose-800",
  violet: "border-violet-200 bg-violet-50 text-violet-800",
  slate: "border-slate-200 bg-slate-50 text-slate-800"
};

export function MetricCard({ label, value, accent }: MetricCardProps) {
  return (
    <div className={`rounded border px-4 py-3 ${accentClasses[accent]}`}>
      <div className="text-xs font-medium uppercase tracking-normal opacity-80">{label}</div>
      <div className="mt-2 text-2xl font-semibold tracking-normal">{value}</div>
    </div>
  );
}

