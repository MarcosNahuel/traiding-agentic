"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/ui/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";

interface SourceDetail {
  id: string;
  url: string;
  title: string | null;
  authors: string | null;
  publication_year: number | null;
  source_type: string;
  status: string;
  relevance_score: number | null;
  credibility_score: number | null;
  applicability_score: number | null;
  overall_score: number | null;
  tags: string[] | null;
  summary: string | null;
  evaluation_reasoning: string | null;
  rejection_reason: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export default function SourceDetailPage() {
  const params = useParams<{ id: string }>();
  const sourceId = params.id;

  const [source, setSource] = useState<SourceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<"evaluate" | "extract" | null>(
    null
  );

  const fetchSource = useCallback(async () => {
    if (!sourceId) return;
    try {
      setLoading(true);
      setError(null);

      const res = await fetch(`/api/sources/${sourceId}`, { cache: "no-store" });
      const payload = (await res.json()) as {
        source?: SourceDetail;
        error?: string;
      };

      if (!res.ok || !payload.source) {
        throw new Error(payload.error ?? "No se pudo cargar el source");
      }

      setSource(payload.source);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error inesperado");
    } finally {
      setLoading(false);
    }
  }, [sourceId]);

  useEffect(() => {
    void fetchSource();
  }, [fetchSource]);

  const runAction = async (type: "evaluate" | "extract") => {
    if (!sourceId) return;
    try {
      setPendingAction(type);
      const endpoint =
        type === "evaluate"
          ? `/api/sources/${sourceId}/evaluate`
          : `/api/sources/${sourceId}/extract`;

      const res = await fetch(endpoint, { method: "POST" });
      const payload = (await res.json()) as { error?: string };
      if (!res.ok) {
        throw new Error(payload.error ?? "La accion fallo");
      }
      await fetchSource();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error inesperado");
    } finally {
      setPendingAction(null);
    }
  };

  return (
    <AppShell
      title={source?.title ?? "Source Detail"}
      description={source?.url ?? "Detalle de la fuente seleccionada."}
      actions={
        <Link
          href="/sources"
          className="rounded-md border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10"
        >
          Volver
        </Link>
      }
    >
      {loading ? (
        <div className="rounded-xl border border-white/10 bg-white/5 p-8 text-sm text-slate-300">
          Cargando detalle...
        </div>
      ) : null}

      {!loading && !source ? (
        <EmptyState
          title="Source no encontrado"
          description="No se encontro el registro solicitado."
          action={
            <Link
              href="/sources"
              className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-medium text-slate-950 hover:bg-cyan-400"
            >
              Ir a Sources
            </Link>
          }
        />
      ) : null}

      {error ? (
        <div className="mb-4 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      {source ? (
        <div className="space-y-4">
          <section className="grid grid-cols-1 gap-3 md:grid-cols-4">
            <DetailCard label="Tipo" value={source.source_type} />
            <DetailCard
              label="Score"
              value={
                source.overall_score != null
                  ? source.overall_score.toFixed(1)
                  : "-"
              }
            />
            <DetailCard
              label="Publicado"
              value={source.publication_year?.toString() ?? "-"}
            />
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-400">
                Estado
              </p>
              <div className="mt-2">
                <StatusBadge status={source.status} />
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-white/10 bg-black/30 p-5">
            <h2 className="text-lg font-semibold text-white">Acciones</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                onClick={() => void runAction("evaluate")}
                disabled={pendingAction !== null}
                className="rounded-md border border-blue-300/30 px-3 py-2 text-sm text-blue-200 disabled:opacity-60"
              >
                {pendingAction === "evaluate" ? "Evaluando..." : "Evaluate"}
              </button>
              <button
                onClick={() => void runAction("extract")}
                disabled={pendingAction !== null || source.status !== "approved"}
                className="rounded-md border border-emerald-300/30 px-3 py-2 text-sm text-emerald-200 disabled:opacity-50"
              >
                {pendingAction === "extract" ? "Extrayendo..." : "Extract"}
              </button>
              <a
                href={source.url}
                target="_blank"
                rel="noreferrer"
                className="rounded-md border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10"
              >
                Abrir URL
              </a>
            </div>
          </section>

          <section className="rounded-xl border border-white/10 bg-black/30 p-5">
            <h2 className="text-lg font-semibold text-white">Evaluacion</h2>
            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
              <DetailCard
                label="Relevance"
                value={
                  source.relevance_score != null
                    ? source.relevance_score.toFixed(1)
                    : "-"
                }
              />
              <DetailCard
                label="Credibility"
                value={
                  source.credibility_score != null
                    ? source.credibility_score.toFixed(1)
                    : "-"
                }
              />
              <DetailCard
                label="Applicability"
                value={
                  source.applicability_score != null
                    ? source.applicability_score.toFixed(1)
                    : "-"
                }
              />
            </div>
            {source.summary ? (
              <p className="mt-4 text-sm text-slate-200">{source.summary}</p>
            ) : null}
            {source.evaluation_reasoning ? (
              <p className="mt-3 text-sm text-slate-300">
                {source.evaluation_reasoning}
              </p>
            ) : null}
            {source.rejection_reason ? (
              <p className="mt-3 rounded-md border border-amber-400/30 bg-amber-500/10 p-3 text-sm text-amber-200">
                Rejection reason: {source.rejection_reason}
              </p>
            ) : null}
            {source.error_message ? (
              <p className="mt-3 rounded-md border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-200">
                Error: {source.error_message}
              </p>
            ) : null}
            {source.tags && source.tags.length > 0 ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {source.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-cyan-400/30 bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-200"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            ) : null}
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}

function DetailCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-lg font-semibold text-white">{value}</p>
    </div>
  );
}
