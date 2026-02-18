"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/ui/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";

interface Guide {
  id: string;
  version: number;
  based_on_sources: number;
  based_on_strategies: number;
  confidence_score: number | null;
  executive_summary: string | null;
  full_guide_markdown: string;
  created_at: string;
}

interface GuidesResponse {
  guides: Guide[];
}

export default function GuidesPage() {
  const [guides, setGuides] = useState<Guide[]>([]);
  const [selectedGuideId, setSelectedGuideId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [synthesizing, setSynthesizing] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const fetchGuides = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch("/api/guides", { cache: "no-store" });
      const payload = (await res.json()) as GuidesResponse | { error: string };

      if (!res.ok || !("guides" in payload)) {
        throw new Error(
          "error" in payload ? payload.error : "No se pudieron cargar guias"
        );
      }

      const items = payload.guides ?? [];
      setGuides(items);
      if (items.length > 0) {
        setSelectedGuideId((prev) =>
          prev && items.some((guide) => guide.id === prev) ? prev : items[0].id
        );
      } else {
        setSelectedGuideId(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error inesperado");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchGuides();
  }, []);

  const selectedGuide = useMemo(
    () => guides.find((guide) => guide.id === selectedGuideId) ?? null,
    [guides, selectedGuideId]
  );

  const triggerSynthesis = async () => {
    try {
      setSynthesizing(true);
      setStatusMessage(null);
      setError(null);

      const res = await fetch("/api/guides/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          minConfidence: 6,
          minEvidenceStrength: "moderate",
        }),
      });

      const payload = (await res.json()) as { error?: string; message?: string };
      if (!res.ok) {
        throw new Error(payload.error ?? "No se pudo iniciar synthesis");
      }

      setStatusMessage(payload.message ?? "Synthesis iniciada.");

      // Poll with early exit when new guide is detected
      const prevCount = guides.length;
      for (let attempt = 0; attempt < 15; attempt++) {
        const delay = Math.min(2000 * Math.pow(1.3, attempt), 10000);
        await new Promise((resolve) => setTimeout(resolve, delay));
        await fetchGuides();
        if (guides.length > prevCount) break;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error inesperado");
    } finally {
      setSynthesizing(false);
    }
  };

  return (
    <AppShell
      title="Guides"
      description="Versiones de guias sintetizadas a partir de las estrategias detectadas."
      actions={
        <button
          onClick={() => void triggerSynthesis()}
          disabled={synthesizing}
          className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-cyan-400 disabled:opacity-60"
        >
          {synthesizing ? "Sintetizando..." : "Generar Nueva Guia"}
        </button>
      }
    >
      {statusMessage ? (
        <div className="mb-4 rounded-xl border border-emerald-400/30 bg-emerald-500/10 p-4 text-sm text-emerald-200">
          {statusMessage}
        </div>
      ) : null}

      {error ? (
        <div className="mb-4 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-xl border border-white/10 bg-white/5 p-8 text-sm text-slate-300">
          Cargando guias...
        </div>
      ) : null}

      {!loading && guides.length === 0 ? (
        <EmptyState
          title="No hay guias generadas"
          description="Ejecuta una sintesis para generar la primera version de la guia de trading."
          action={
            <button
              onClick={() => void triggerSynthesis()}
              disabled={synthesizing}
              className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-cyan-400 disabled:opacity-60"
            >
              {synthesizing ? "Sintetizando..." : "Generar Guia"}
            </button>
          }
        />
      ) : null}

      {!loading && guides.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <aside className="rounded-xl border border-white/10 bg-black/30 p-4 lg:col-span-4">
            <h2 className="mb-3 text-sm uppercase tracking-wide text-slate-300">
              Versiones
            </h2>
            <ul className="space-y-2">
              {guides.map((guide) => {
                const active = selectedGuideId === guide.id;
                return (
                  <li key={guide.id}>
                    <button
                      onClick={() => setSelectedGuideId(guide.id)}
                      className={`w-full rounded-md border px-3 py-2 text-left text-sm transition ${
                        active
                          ? "border-cyan-400/40 bg-cyan-500/10 text-cyan-200"
                          : "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10"
                      }`}
                    >
                      <p className="font-medium">Version {guide.version}</p>
                      <p className="mt-0.5 text-xs text-slate-300">
                        {new Date(guide.created_at).toLocaleString()}
                      </p>
                      <p className="mt-1 text-xs text-slate-400">
                        {guide.based_on_sources} fuentes /{" "}
                        {guide.based_on_strategies} estrategias
                      </p>
                    </button>
                  </li>
                );
              })}
            </ul>
          </aside>

          <section className="rounded-xl border border-white/10 bg-black/30 p-5 lg:col-span-8">
            {selectedGuide ? (
              <>
                <div className="mb-4 flex flex-wrap items-end justify-between gap-3 border-b border-white/10 pb-3">
                  <div>
                    <h2 className="text-xl font-semibold text-white">
                      Trading Guide v{selectedGuide.version}
                    </h2>
                    <p className="text-sm text-slate-300">
                      Confianza:{" "}
                      {selectedGuide.confidence_score != null
                        ? `${selectedGuide.confidence_score.toFixed(1)} / 10`
                        : "N/A"}
                    </p>
                  </div>
                </div>

                {selectedGuide.executive_summary ? (
                  <p className="mb-4 rounded-md border border-white/10 bg-white/5 p-3 text-sm text-slate-200">
                    {selectedGuide.executive_summary}
                  </p>
                ) : null}

                <pre className="max-h-[65vh] overflow-auto whitespace-pre-wrap rounded-md border border-white/10 bg-slate-950/70 p-4 text-sm leading-relaxed text-slate-100">
                  {selectedGuide.full_guide_markdown}
                </pre>
              </>
            ) : (
              <p className="text-sm text-slate-300">Selecciona una guia.</p>
            )}
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}

