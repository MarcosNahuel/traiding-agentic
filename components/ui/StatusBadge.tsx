interface StatusBadgeProps {
  status: string | null | undefined;
  variant?: "success" | "warning" | "error" | "info";
}

const STATUS_CLASS: Record<string, string> = {
  pending: "bg-amber-500/20 text-amber-200 border-amber-400/40",
  fetching: "bg-sky-500/20 text-sky-200 border-sky-400/40",
  evaluating: "bg-blue-500/20 text-blue-200 border-blue-400/40",
  approved: "bg-emerald-500/20 text-emerald-200 border-emerald-400/40",
  processing: "bg-indigo-500/20 text-indigo-200 border-indigo-400/40",
  processed: "bg-green-500/20 text-green-200 border-green-400/40",
  rejected: "bg-rose-500/20 text-rose-200 border-rose-400/40",
  error: "bg-red-500/20 text-red-200 border-red-400/40",
  started: "bg-blue-500/20 text-blue-200 border-blue-400/40",
  success: "bg-emerald-500/20 text-emerald-200 border-emerald-400/40",
  warning: "bg-amber-500/20 text-amber-200 border-amber-400/40",
  weak: "bg-amber-500/20 text-amber-200 border-amber-400/40",
  moderate: "bg-sky-500/20 text-sky-200 border-sky-400/40",
  strong: "bg-emerald-500/20 text-emerald-200 border-emerald-400/40",
};

function formatStatus(status: string): string {
  return status
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

const VARIANT_CLASS: Record<string, string> = {
  success: "bg-emerald-500/20 text-emerald-200 border-emerald-400/40",
  warning: "bg-amber-500/20 text-amber-200 border-amber-400/40",
  error: "bg-red-500/20 text-red-200 border-red-400/40",
  info: "bg-sky-500/20 text-sky-200 border-sky-400/40",
};

export function StatusBadge({ status, variant }: StatusBadgeProps) {
  const value = (status ?? "unknown").toLowerCase();
  const className = variant
    ? VARIANT_CLASS[variant]
    : STATUS_CLASS[value] ??
      "bg-slate-500/20 text-slate-200 border-slate-400/40";

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${className}`}
    >
      {formatStatus(value)}
    </span>
  );
}
