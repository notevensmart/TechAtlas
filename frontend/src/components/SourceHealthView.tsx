import { AlertTriangle, CheckCircle2, CircleDashed, Loader2, type LucideIcon } from "lucide-react";
import type { SourceHealthItem } from "../types/api";
import { formatDate, formatDateTime, formatNumber } from "../utils/format";
import { EmptyState } from "./EmptyState";
import { MetricCard } from "./MetricCard";

interface SourceHealthViewProps {
  data?: SourceHealthItem[];
  thirtyDayData?: SourceHealthItem[];
  isLoading: boolean;
  isError: boolean;
}

const qualityClasses = {
  high: "border-teal-200 bg-teal-50 text-teal-800",
  medium: "border-amber-200 bg-amber-50 text-amber-800",
  low: "border-rose-200 bg-rose-50 text-rose-800"
};

const statusClasses = {
  completed: "border-teal-200 bg-teal-50 text-teal-800",
  failed: "border-rose-200 bg-rose-50 text-rose-800",
  running: "border-sky-200 bg-sky-50 text-sky-800",
  "zero rows": "border-amber-200 bg-amber-50 text-amber-800",
  "zero import": "border-amber-200 bg-amber-50 text-amber-800",
  "not crawled": "border-slate-200 bg-slate-50 text-slate-700"
};

function latestDate(items: SourceHealthItem[]): string | null {
  const timestamps = items
    .map((item) => item.latest_crawl_finished_at)
    .filter((value): value is string => Boolean(value))
    .map((value) => new Date(value).getTime());
  if (!timestamps.length) return null;
  return new Date(Math.max(...timestamps)).toISOString();
}

function statusLabel(item: SourceHealthItem): keyof typeof statusClasses {
  if (!item.latest_status) return "not crawled";
  if (item.latest_status === "completed" && item.rows_extracted === 0) return "zero rows";
  if (item.latest_status === "completed" && item.rows_imported === 0) return "zero import";
  if (item.latest_status in statusClasses) return item.latest_status as keyof typeof statusClasses;
  return "not crawled";
}

function isFailedOrZeroYield(item: SourceHealthItem): boolean {
  const status = statusLabel(item);
  return status === "failed" || status === "zero rows" || status === "zero import";
}

function dateOrNA(value: string | null): string {
  return value ? formatDate(value) : "n/a";
}

function Badge({
  label,
  className,
  icon: Icon
}: {
  label: string;
  className: string;
  icon?: LucideIcon;
}) {
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-2 py-1 text-xs font-medium ${className}`}>
      {Icon ? <Icon className="h-3.5 w-3.5" aria-hidden="true" /> : null}
      {label}
    </span>
  );
}

export function SourceHealthView({ data, thirtyDayData, isLoading, isError }: SourceHealthViewProps) {
  const items = data ?? [];
  const thirtyDayItems = thirtyDayData ?? [];
  const activeSources = items.filter((item) => item.total_listings > 0).length;
  const successfulSources = items.filter((item) => item.latest_status === "completed").length;
  const thirtyDayPostings = thirtyDayItems.reduce((sum, item) => sum + item.period_listings, 0);
  const failedOrZero = items.filter(isFailedOrZeroYield).length;
  const latestCrawl = latestDate(items);

  if (isLoading) {
    return (
      <div className="flex min-h-48 items-center justify-center rounded border border-line bg-white p-6 text-sm text-slate-600">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
        Loading source coverage
      </div>
    );
  }

  if (isError) {
    return (
      <EmptyState
        title="Source health unavailable"
        message="Start the FastAPI backend and confirm the database has the latest migrations."
      />
    );
  }

  if (!items.length) {
    return (
      <EmptyState
        title="No source coverage records"
        message="Add enabled entries to ingestion/sources.yml, then run python -m ingestion.cli crawl-all --canonical-output data/crawl_all_rows.jsonl --rejects-dir data/rejects."
      />
    );
  }

  return (
    <div className="grid gap-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard label="Active sources" value={formatNumber(activeSources)} accent="teal" />
        <MetricCard label="Successful crawls" value={formatNumber(successfulSources)} accent="sky" />
        <MetricCard label="30d postings covered" value={formatNumber(thirtyDayPostings)} accent="amber" />
        <MetricCard label="Latest crawl" value={formatDateTime(latestCrawl)} accent="violet" />
        <MetricCard label="Failed/zero-yield" value={formatNumber(failedOrZero)} accent="rose" />
      </div>

      <div className="rounded border border-line bg-white">
        <div className="border-b border-line p-4">
          <h2 className="text-base font-semibold text-ink">Data Coverage</h2>
          <p className="mt-1 text-sm text-slate-600">{items.length} configured or observed sources match the current filters.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-line text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-normal text-slate-500">
              <tr>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Adapter</th>
                <th className="px-4 py-3">Quality</th>
                <th className="px-4 py-3">Listings</th>
                <th className="px-4 py-3">Selected range listings</th>
                <th className="px-4 py-3">Latest listing</th>
                <th className="px-4 py-3">Last crawl</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {items.map((item) => {
                const status = statusLabel(item);
                const quality = (item.quality_tier in qualityClasses ? item.quality_tier : "low") as keyof typeof qualityClasses;
                const StatusIcon =
                  status === "completed" ? CheckCircle2 : status === "failed" ? AlertTriangle : CircleDashed;
                return (
                  <tr key={item.source} className="align-top hover:bg-slate-50">
                    <td className="max-w-xs px-4 py-3">
                      <div className="break-words font-medium text-ink">{item.source}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        {item.pages_fetched} fetched, {item.pages_skipped} skipped
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{item.adapter ?? "n/a"}</td>
                    <td className="px-4 py-3">
                      <Badge label={quality} className={qualityClasses[quality]} />
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      <div className="font-medium text-ink">{formatNumber(item.total_listings)}</div>
                      <div className="mt-1 text-xs text-slate-500">first {dateOrNA(item.first_listing_listed_at)}</div>
                    </td>
                    <td className="px-4 py-3 font-medium text-ink">{formatNumber(item.period_listings)}</td>
                    <td className="px-4 py-3 text-slate-700">{dateOrNA(item.latest_listing_listed_at)}</td>
                    <td className="px-4 py-3 text-slate-700">{formatDateTime(item.latest_crawl_finished_at)}</td>
                    <td className="px-4 py-3">
                      <div className="grid gap-2">
                        <Badge label={status} className={statusClasses[status]} icon={StatusIcon} />
                        <div className="text-xs text-slate-500">
                          {formatNumber(item.rows_extracted)} extracted, {formatNumber(item.rows_imported)} imported
                        </div>
                      </div>
                    </td>
                    <td className="min-w-72 max-w-md px-4 py-3 text-slate-600">{item.notes ?? "n/a"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
