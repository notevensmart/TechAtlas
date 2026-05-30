import { Database } from "lucide-react";

interface EmptyStateProps {
  title: string;
  message: string;
}

export function EmptyState({ title, message }: EmptyStateProps) {
  return (
    <div className="flex min-h-48 items-center justify-center rounded border border-dashed border-line bg-white px-6 py-10 text-center">
      <div className="max-w-md">
        <Database className="mx-auto mb-3 h-7 w-7 text-slate-400" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">{message}</p>
      </div>
    </div>
  );
}

