import { ExternalLink, Search, X } from "lucide-react";
import { useState } from "react";
import type { ListingItem, ListingsResponse } from "../types/api";
import { formatCurrency, formatDate } from "../utils/format";
import { EmptyState } from "./EmptyState";

interface ListingsTableProps {
  data?: ListingsResponse;
  search: string;
  onSearch: (value: string) => void;
  page: number;
  onPage: (page: number) => void;
}

export function ListingsTable({ data, search, onSearch, page, onPage }: ListingsTableProps) {
  const [selected, setSelected] = useState<ListingItem | null>(null);
  const items = data?.items ?? [];

  return (
    <div className="rounded border border-line bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Listings</h2>
          <p className="text-sm text-slate-600">{data?.total ?? 0} postings match the current filters.</p>
        </div>
        <label className="relative w-full max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
          <input
            className="focus-ring h-9 w-full rounded border border-line pl-9 pr-3 text-sm"
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            placeholder="Search title, company, description"
          />
        </label>
      </div>
      {!items.length ? (
        <div className="p-4">
          <EmptyState title="No listings found" message="Import real listings or loosen the filters to inspect records." />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-line text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-normal text-slate-500">
              <tr>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Company</th>
                <th className="px-4 py-3">City</th>
                <th className="px-4 py-3">Listed</th>
                <th className="px-4 py-3">Salary</th>
                <th className="px-4 py-3">Skills</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50">
                  <td className="max-w-xs px-4 py-3">
                    <button
                      type="button"
                      className="focus-ring text-left font-medium text-sky-700 hover:text-sky-900"
                      onClick={() => setSelected(item)}
                    >
                      {item.title}
                    </button>
                    <div className="mt-1 text-xs text-slate-500">{item.role_family}</div>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{item.company}</td>
                  <td className="px-4 py-3 text-slate-700">{item.city}</td>
                  <td className="px-4 py-3 text-slate-700">{formatDate(item.listed_at)}</td>
                  <td className="px-4 py-3 text-slate-700">{formatCurrency(item.salary_mid_annual)}</td>
                  <td className="max-w-sm px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {item.skills.slice(0, 5).map((skill) => (
                        <span key={skill} className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-700">
                          {skill}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="flex items-center justify-between border-t border-line p-4 text-sm text-slate-600">
        <span>
          Page {data?.page ?? page} of {data?.total_pages ?? 1}
        </span>
        <div className="flex gap-2">
          <button
            className="focus-ring rounded border border-line px-3 py-1.5 disabled:opacity-40"
            type="button"
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
          >
            Previous
          </button>
          <button
            className="focus-ring rounded border border-line px-3 py-1.5 disabled:opacity-40"
            type="button"
            disabled={!data || page >= data.total_pages}
            onClick={() => onPage(page + 1)}
          >
            Next
          </button>
        </div>
      </div>

      {selected ? (
        <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/25" role="dialog" aria-modal="true">
          <div className="h-full w-full max-w-xl overflow-y-auto bg-white shadow-xl">
            <div className="sticky top-0 flex items-start justify-between gap-4 border-b border-line bg-white p-5">
              <div>
                <h3 className="text-lg font-semibold text-ink">{selected.title}</h3>
                <p className="mt-1 text-sm text-slate-600">{selected.company}</p>
              </div>
              <button
                type="button"
                className="focus-ring rounded p-2 text-slate-500 hover:bg-slate-100"
                onClick={() => setSelected(null)}
                aria-label="Close listing detail"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            <div className="grid gap-5 p-5">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <Info label="Source" value={selected.source} />
                <Info label="Listed" value={formatDate(selected.listed_at)} />
                <Info label="Location" value={selected.raw_location} />
                <Info label="Work mode" value={selected.work_mode} />
                <Info label="Experience" value={selected.experience_level} />
                <Info label="Salary" value={formatCurrency(selected.salary_mid_annual)} />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-ink">Detected Skills</h4>
                <div className="mt-2 flex flex-wrap gap-2">
                  {selected.skills.length ? (
                    selected.skills.map((skill) => (
                      <span key={skill} className="rounded bg-teal-50 px-2 py-1 text-xs font-medium text-teal-800">
                        {skill}
                      </span>
                    ))
                  ) : (
                    <span className="text-sm text-slate-500">No taxonomy skills detected.</span>
                  )}
                </div>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-ink">Description Snippet</h4>
                <p className="mt-2 whitespace-pre-line text-sm leading-6 text-slate-700">{selected.description_snippet}</p>
              </div>
              {selected.source_url ? (
                <a
                  className="focus-ring inline-flex w-fit items-center gap-2 rounded bg-ink px-3 py-2 text-sm font-medium text-white"
                  href={selected.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  <ExternalLink className="h-4 w-4" aria-hidden="true" />
                  Open source listing
                </a>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-line p-3">
      <div className="text-xs font-medium uppercase tracking-normal text-slate-500">{label}</div>
      <div className="mt-1 break-words text-sm font-medium text-ink">{value}</div>
    </div>
  );
}

