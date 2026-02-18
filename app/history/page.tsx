"use client";

import { useState } from "react";
import useSWR from "swr";
import { AppShell } from "@/components/ui/AppShell";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-slate-500/20 text-slate-400",
  validated: "bg-blue-500/20 text-blue-400",
  approved: "bg-emerald-500/20 text-emerald-400",
  rejected: "bg-orange-500/20 text-orange-400",
  executed: "bg-green-500/20 text-green-300",
  error: "bg-red-500/20 text-red-400",
  dead_letter: "bg-red-600/20 text-red-300",
  cancelled: "bg-gray-500/20 text-gray-400",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[status] || "bg-gray-500/20 text-gray-400"}`}>
      {status}
    </span>
  );
}

export default function HistoryPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [symbolFilter, setSymbolFilter] = useState<string>("");

  const { data: proposalsData, mutate: mutateProposals } = useSWR(
    "/api/trades/proposals?limit=200",
    fetcher,
    { refreshInterval: 30000 }
  );

  const { data: reconData } = useSWR("/api/reconciliation/history", fetcher, {
    refreshInterval: 60000,
  });

  const { data: deadLetterData, mutate: mutateDL } = useSWR(
    "/api/dead-letters",
    fetcher,
    { refreshInterval: 30000 }
  );

  const proposals = proposalsData?.proposals || proposalsData || [];
  const reconRuns = reconData?.runs || [];
  const deadLetters = deadLetterData?.dead_letters || [];

  // Filter proposals
  const filtered = Array.isArray(proposals)
    ? proposals.filter((p: any) => {
        if (statusFilter !== "all" && p.status !== statusFilter) return false;
        if (symbolFilter && !p.symbol?.includes(symbolFilter.toUpperCase()))
          return false;
        return true;
      })
    : [];

  const handleRetry = async (id: string) => {
    try {
      await fetch(`/api/dead-letters/${id}/retry`, { method: "POST" });
      mutateDL();
      mutateProposals();
    } catch (e) {
      alert("Retry failed: " + (e instanceof Error ? e.message : String(e)));
    }
  };

  const handleCancel = async (id: string) => {
    try {
      await fetch(`/api/dead-letters/${id}/cancel`, { method: "POST" });
      mutateDL();
      mutateProposals();
    } catch (e) {
      alert("Cancel failed: " + (e instanceof Error ? e.message : String(e)));
    }
  };

  const handleExport = () => {
    const params = new URLSearchParams();
    if (statusFilter !== "all") params.set("status", statusFilter);
    window.open(`/api/trades/export?${params.toString()}`, "_blank");
  };

  return (
    <AppShell
      title="History"
      description="Trade timeline, reconciliation runs, and dead-letter management"
      actions={
        <button
          onClick={handleExport}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 transition-colors"
        >
          Export CSV
        </button>
      }
    >
      {/* Dead Letters Section */}
      {deadLetters.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-4 text-lg font-semibold text-red-400">
            Dead Letters ({deadLetters.length})
          </h2>
          <div className="overflow-x-auto rounded-xl border border-red-500/20 bg-red-950/10">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5 text-left text-xs text-slate-400">
                  <th className="px-4 py-3">Symbol</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Quantity</th>
                  <th className="px-4 py-3">Retries</th>
                  <th className="px-4 py-3">Error</th>
                  <th className="px-4 py-3">Updated</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {deadLetters.map((dl: any) => (
                  <tr key={dl.id} className="border-b border-white/5 hover:bg-white/[0.02]">
                    <td className="px-4 py-3 font-mono text-white">{dl.symbol}</td>
                    <td className="px-4 py-3">
                      <span className={dl.type === "buy" ? "text-emerald-400" : "text-red-400"}>
                        {dl.type?.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-300">{dl.quantity}</td>
                    <td className="px-4 py-3 text-slate-400">{dl.retry_count}</td>
                    <td className="px-4 py-3 max-w-[200px] truncate text-red-400/80 text-xs" title={dl.error_message}>
                      {dl.error_message}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {dl.updated_at ? new Date(dl.updated_at).toLocaleString() : "-"}
                    </td>
                    <td className="px-4 py-3 space-x-2">
                      <button onClick={() => handleRetry(dl.id)} className="rounded bg-emerald-600/80 px-2.5 py-1 text-xs text-white hover:bg-emerald-500">
                        Retry
                      </button>
                      <button onClick={() => handleCancel(dl.id)} className="rounded bg-slate-600/80 px-2.5 py-1 text-xs text-white hover:bg-slate-500">
                        Cancel
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Reconciliation Section */}
      <section className="mb-8">
        <h2 className="mb-4 text-lg font-semibold text-white">
          Recent Reconciliation Runs
        </h2>
        <div className="overflow-x-auto rounded-xl border border-white/5 bg-white/[0.02]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/5 text-left text-xs text-slate-400">
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Orders</th>
                <th className="px-4 py-3">Positions</th>
                <th className="px-4 py-3">Divergences</th>
                <th className="px-4 py-3">Duration</th>
              </tr>
            </thead>
            <tbody>
              {reconRuns.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-500">No reconciliation runs yet</td></tr>
              ) : (
                reconRuns.slice(0, 5).map((r: any) => (
                  <tr key={r.id} className="border-b border-white/5 hover:bg-white/[0.02]">
                    <td className="px-4 py-3 text-xs text-slate-400">
                      {r.created_at ? new Date(r.created_at).toLocaleString() : "-"}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-medium ${r.status === "success" ? "text-emerald-400" : r.status === "error" ? "text-red-400" : "text-yellow-400"}`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-300">{r.orders_synced}</td>
                    <td className="px-4 py-3 text-slate-300">{r.positions_synced}</td>
                    <td className="px-4 py-3">
                      <span className={r.divergences_found > 0 ? "text-red-400 font-semibold" : "text-slate-400"}>
                        {r.divergences_found}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">{r.duration_ms}ms</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Trade Timeline Section */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Trade Timeline</h2>
          <div className="flex gap-3">
            <input
              type="text"
              placeholder="Filter symbol..."
              value={symbolFilter}
              onChange={(e) => setSymbolFilter(e.target.value)}
              className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white placeholder:text-slate-500 focus:border-emerald-500/50 focus:outline-none"
            />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white focus:border-emerald-500/50 focus:outline-none"
            >
              <option value="all">All statuses</option>
              <option value="draft">Draft</option>
              <option value="validated">Validated</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="executed">Executed</option>
              <option value="error">Error</option>
              <option value="dead_letter">Dead Letter</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto rounded-xl border border-white/5 bg-white/[0.02]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/5 text-left text-xs text-slate-400">
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">Symbol</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Qty</th>
                <th className="px-4 py-3">Price</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Exec Price</th>
                <th className="px-4 py-3">Commission</th>
                <th className="px-4 py-3">Executed At</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={9} className="px-4 py-8 text-center text-slate-500">No proposals found</td></tr>
              ) : (
                filtered.map((p: any) => (
                  <tr key={p.id} className="border-b border-white/5 hover:bg-white/[0.02]">
                    <td className="px-4 py-3 text-xs text-slate-400">
                      {p.created_at ? new Date(p.created_at).toLocaleString() : "-"}
                    </td>
                    <td className="px-4 py-3 font-mono text-white">{p.symbol}</td>
                    <td className="px-4 py-3">
                      <span className={p.type === "buy" ? "text-emerald-400" : "text-red-400"}>
                        {p.type?.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-300">{p.quantity}</td>
                    <td className="px-4 py-3 font-mono text-slate-300">{p.price ? `$${Number(p.price).toFixed(2)}` : "-"}</td>
                    <td className="px-4 py-3"><StatusBadge status={p.status} /></td>
                    <td className="px-4 py-3 font-mono text-slate-300">
                      {p.executed_price ? `$${Number(p.executed_price).toFixed(2)}` : "-"}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">
                      {p.commission ? `${Number(p.commission).toFixed(6)} ${p.commission_asset || ""}` : "-"}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">
                      {p.executed_at ? new Date(p.executed_at).toLocaleString() : "-"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Showing {filtered.length} of {Array.isArray(proposals) ? proposals.length : 0} proposals
        </p>
      </section>
    </AppShell>
  );
}
