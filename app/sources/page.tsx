"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/ui/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";

interface Source {
  id: string;
  url: string;
  title: string | null;
  source_type: string;
  status: string;
  overall_score: number | null;
  relevance_score: number | null;
  credibility_score: number | null;
  applicability_score: number | null;
  created_at: string;
  updated_at: string;
  error_message: string | null;
}

interface SourcesResponse {
  sources: Source[];
  total: number;
  limit: number;
  offset: number;
}

const STATUS_OPTIONS = [
  "all",
  "pending",
  "fetching",
  "evaluating",
  "approved",
  "processing",
  "processed",
  "rejected",
  "error",
];

const SOURCE_TYPES = ["all", "paper", "article", "repo", "book", "video"];

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [pendingAction, setPendingAction] = useState<{
    id: string;
    type: "evaluate" | "extract";
  } | null>(null);

  const fetchSources = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch("/api/sources?limit=200", { cache: "no-store" });
      const payload = (await res.json()) as SourcesResponse | { error: string };

      if (!res.ok || !("sources" in payload)) {
        throw new Error(
          "error" in payload ? payload.error : "No se pudo cargar sources"
        );
      }

      setSources(payload.sources ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error inesperado");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchSources();
  }, []);

  const filteredSources = useMemo(() => {
    const q = query.trim().toLowerCase();
    return sources.filter((source) => {
      const byStatus = statusFilter === "all" || source.status === statusFilter;
      const byType = typeFilter === "all" || source.source_type === typeFilter;
      const byQuery =
        !q ||
        source.url.toLowerCase().includes(q) ||
        (source.title ?? "").toLowerCase().includes(q);
      return byStatus && byType && byQuery;
    });
  }, [sources, query, statusFilter, typeFilter]);

  const counters = useMemo(() => {
    const acc: Record<string, number> = {};
    for (const source of sources) {
      acc[source.status] = (acc[source.status] ?? 0) + 1;
    }
    return {
      total: sources.length,
      approved: acc.approved ?? 0,
      processed: acc.processed ?? 0,
      errors: acc.error ?? 0,
    };
  }, [sources]);

  const runAction = async (sourceId: string, type: "evaluate" | "extract") => {
    try {
      setPendingAction({ id: sourceId, type });
      const endpoint =
        type === "evaluate"
          ? `/api/sources/${sourceId}/evaluate`
          : `/api/sources/${sourceId}/extract`;

      const res = await fetch(endpoint, { method: "POST" });
      const payload = (await res.json()) as { error?: string };
      if (!res.ok) {
        throw new Error(payload.error ?? "La accion fallo");
      }

      await fetchSources();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error inesperado");
    } finally {
      setPendingAction(null);
    }
  };

  return (
    <AppShell
      title="Sources"
      description="Gestion de papers, articulos y repos que alimentan el pipeline."
      actions={
        <Link
          href="/sources/new"
          className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-cyan-400"
        >
          Agregar Source
        </Link>
      }
    >
      <section className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label="Total" value={counters.total} />
        <MetricCard label="Approved" value={counters.approved} />
        <MetricCard label="Processed" value={counters.processed} />
        <MetricCard label="Errores" value={counters.errors} />
      </section>

      <section className="mb-4 grid grid-cols-1 gap-3 rounded-xl border border-white/10 bg-white/5 p-4 md:grid-cols-4">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar por URL o titulo"
          className="rounded-md border border-white/15 bg-black/30 px-3 py-2 text-sm text-white outline-none ring-cyan-400 transition focus:ring-2"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-white/15 bg-black/30 px-3 py-2 text-sm text-white outline-none ring-cyan-400 transition focus:ring-2"
        >
          {STATUS_OPTIONS.map((status) => (
            <option key={status} value={status} className="bg-slate-900">
              Estado: {status}
            </option>
          ))}
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="rounded-md border border-white/15 bg-black/30 px-3 py-2 text-sm text-white outline-none ring-cyan-400 transition focus:ring-2"
        >
          {SOURCE_TYPES.map((type) => (
            <option key={type} value={type} className="bg-slate-900">
              Tipo: {type}
            </option>
          ))}
        </select>
        <button
          onClick={() => void fetchSources()}
          className="rounded-md border border-white/20 px-3 py-2 text-sm text-white transition hover:bg-white/10"
        >
          Refrescar
        </button>
      </section>

      {loading ? (
        <div className="rounded-xl border border-white/10 bg-white/5 p-8 text-sm text-slate-300">
          Cargando sources...
        </div>
      ) : null}

      {error ? (
        <div className="mb-4 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      {!loading && filteredSources.length === 0 ? (
        <EmptyState
          title="No hay sources para mostrar"
          description="Ajusta filtros o agrega una nueva fuente para iniciar el pipeline."
          action={
            <Link
              href="/sources/new"
              className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-cyan-400"
            >
              Agregar primer source
            </Link>
          }
        />
      ) : null}

      {!loading && filteredSources.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-white/10 bg-black/30">
          <table className="min-w-full text-sm">
            <thead className="border-b border-white/10 text-left text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Fecha</th>
                <th className="px-4 py-3">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filteredSources.map((source) => {
                const actionBusy = pendingAction?.id === source.id;
                return (
                  <tr
                    key={source.id}
                    className="border-b border-white/5 align-top text-slate-200"
                  >
                    <td className="px-4 py-3">
                      <div className="max-w-sm">
                        <p className="font-medium text-white">
                          {source.title ?? "Sin titulo"}
                        </p>
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                          className="line-clamp-1 text-xs text-cyan-300 hover:text-cyan-200"
                        >
                          {source.url}
                        </a>
                      </div>
                    </td>
                    <td className="px-4 py-3 capitalize">{source.source_type}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={source.status} />
                    </td>
                    <td className="px-4 py-3">
                      {source.overall_score != null
                        ? source.overall_score.toFixed(1)
                        : "-"}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-300">
                      {new Date(source.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2">
                        <Link
                          href={`/sources/${source.id}`}
                          className="rounded-md border border-white/20 px-2.5 py-1 text-xs text-slate-100 hover:bg-white/10"
                        >
                          Ver
                        </Link>
                        <button
                          onClick={() => void runAction(source.id, "evaluate")}
                          disabled={actionBusy}
                          className="rounded-md border border-blue-300/30 px-2.5 py-1 text-xs text-blue-200 disabled:opacity-60"
                        >
                          {actionBusy && pendingAction?.type === "evaluate"
                            ? "Evaluando..."
                            : "Evaluate"}
                        </button>
                        <button
                          onClick={() => void runAction(source.id, "extract")}
                          disabled={actionBusy || source.status !== "approved"}
                          className="rounded-md border border-emerald-300/30 px-2.5 py-1 text-xs text-emerald-200 disabled:opacity-50"
                        >
                          {actionBusy && pendingAction?.type === "extract"
                            ? "Extrayendo..."
                            : "Extract"}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </AppShell>
  );
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

