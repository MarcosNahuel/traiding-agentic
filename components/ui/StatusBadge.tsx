interface StatusBadgeProps {
  status: string | null | undefined;
  variant?: "success" | "warning" | "error" | "info";
}

const STATUS_CLASS: Record<string, string> = {
  pending: "bg-amber-500/10 text-amber-200 border-amber-500/20 shadow-[0_0_10px_rgba(245,158,11,0.1)]",
  fetching: "bg-sky-500/10 text-sky-200 border-sky-500/20",
  evaluating: "bg-blue-500/10 text-blue-200 border-blue-500/20",
  approved: "bg-emerald-500/10 text-emerald-200 border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.1)]",
  processing: "bg-indigo-500/10 text-indigo-200 border-indigo-500/20",
  processed: "bg-teal-500/10 text-teal-200 border-teal-500/20",
  rejected: "bg-rose-500/10 text-rose-200 border-rose-500/20",
  error: "bg-red-500/10 text-red-200 border-red-500/20 shadow-[0_0_10px_rgba(239,68,68,0.1)]",
  started: "bg-blue-500/10 text-blue-200 border-blue-500/20",
  success: "bg-emerald-500/10 text-emerald-200 border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.1)]",
  warning: "bg-amber-500/10 text-amber-200 border-amber-500/20",
  weak: "bg-amber-500/10 text-amber-200 border-amber-500/20",
  moderate: "bg-sky-500/10 text-sky-200 border-sky-500/20",
  strong: "bg-emerald-500/10 text-emerald-200 border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.1)]",
};

function formatStatus(status: string): string {
  return status
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

const VARIANT_CLASS: Record<string, string> = {
  success: "bg-emerald-500/10 text-emerald-200 border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.1)]",
  warning: "bg-amber-500/10 text-amber-200 border-amber-500/20",
  error: "bg-red-500/10 text-red-200 border-red-500/20 shadow-[0_0_10px_rgba(239,68,68,0.1)]",
  info: "bg-sky-500/10 text-sky-200 border-sky-500/20",
};

export function StatusBadge({ status, variant }: StatusBadgeProps) {
  const value = (status ?? "unknown").toLowerCase();
  const className = variant
    ? VARIANT_CLASS[variant]
    : STATUS_CLASS[value] ??
      "bg-slate-500/10 text-slate-200 border-slate-500/20";

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium backdrop-blur-md ${className}`}
    >
      {formatStatus(value)}
    </span>
  );
}
