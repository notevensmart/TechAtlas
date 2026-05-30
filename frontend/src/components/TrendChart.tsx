import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import type { SkillHistoryPoint } from "../types/api";
import { EmptyState } from "./EmptyState";

interface TrendChartProps {
  skill: string | null;
  data: SkillHistoryPoint[];
}

export function TrendChart({ skill, data }: TrendChartProps) {
  if (!skill || !data.length) {
    return (
      <EmptyState
        title="No trend history yet"
        message="Trend lines appear after imported postings produce dated skill snapshots."
      />
    );
  }

  return (
    <div className="h-80 rounded border border-line bg-white p-4">
      <h2 className="text-base font-semibold text-ink">{skill} Trend</h2>
      <p className="mb-3 text-sm text-slate-600">Daily postings mentioning this skill.</p>
      <ResponsiveContainer width="100%" height="82%">
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid stroke="#e6edf3" vertical={false} />
          <XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#64748b" }} />
          <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#64748b" }} />
          <Tooltip />
          <Line type="monotone" dataKey="listing_count" stroke="#2563eb" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

