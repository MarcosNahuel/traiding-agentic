"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/ui/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";

interface StrategySource {
  id: string;
  title: string | null;
  publication_year: number | null;
}

interface Strategy {
  id: string;
  name: string;
  description: string;
  strategy_type: string;
  market: string;
  timeframe: string | null;
  confidence: number;
  evidence_strength: string;
  indicators: string[] | null;
  entry_rules: string[] | null;
  exit_rules: string[] | null;
  limitations: string[] | null;
  source_id: string;
  source: StrategySource | null;
  created_at: string;
}

interface StrategiesResponse {
  strategies: Strategy[];
}

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [minConfidence, setMinConfidence] = useState("1");

  const fetchStrategies = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch("/api/strategies", { cache: "no-store" });
      const payload = (await res.json()) as
        | StrategiesResponse
        | { error: string };

      if (!res.ok || !("strategies" in payload)) {
        throw new Error(
          "error" in payload ? payload.error : "No se pudieron cargar estrategias"
        );
      }

      setStrategies(payload.strategies ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error inesperado");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchStrategies();
  }, []);

  const strategyTypes = useMemo(() => {
    const set = new Set<string>();
    for (const strategy of strategies) {
      set.add(strategy.strategy_type);
    }
    return ["all", ...Array.from(set).sort()];
  }, [strategies]);

  const filteredStrategies = useMemo(() => {
    const q = search.trim().toLowerCase();
    const min = Number.parseFloat(minConfidence) || 1;
    return strategies.filter((strategy) => {
      const byType =
        typeFilter === "all" || strategy.strategy_type === typeFilter;
      const byConfidence = strategy.confidence >= min;
      const byQuery =
        !q ||
        strategy.name.toLowerCase().includes(q) ||
        strategy.description.toLowerCase().includes(q) ||
        (strategy.source?.title ?? "").toLowerCase().includes(q);
      return byType && byConfidence && byQuery;
    });
  }, [strategies, search, typeFilter, minConfidence]);

  return (
    <AppShell
      title="Strategies"
      description="Explora estrategias extraidas por el Reader Agent con su evidencia y nivel de confianza."
      actions={
        <button
          onClick={() => void fetchStrategies()}
          className="rounded-md border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10"
        >
          Refrescar
        </button>
      }
    >
      <section className="mb-4 grid grid-cols-1 gap-3 rounded-xl border border-white/10 bg-white/5 p-4 md:grid-cols-4">
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Buscar estrategia, descripcion o fuente"
          className="rounded-md border border-white/15 bg-black/30 px-3 py-2 text-sm text-white outline-none ring-cyan-400 transition focus:ring-2"
        />
        <select
          value={typeFilter}
          onChange={(event) => setTypeFilter(event.target.value)}
          className="rounded-md border border-white/15 bg-black/30 px-3 py-2 text-sm text-white outline-none ring-cyan-400 transition focus:ring-2"
        >
          {strategyTypes.map((type) => (
            <option key={type} value={type} className="bg-slate-900">
              Tipo: {type}
            </option>
          ))}
        </select>
        <input
          type="number"
          min={1}
          max={10}
          step={1}
          value={minConfidence}
          onChange={(event) => setMinConfidence(event.target.value)}
          className="rounded-md border border-white/15 bg-black/30 px-3 py-2 text-sm text-white outline-none ring-cyan-400 transition focus:ring-2"
          aria-label="Confianza minima"
        />
        <div className="flex items-center text-sm text-slate-300">
          Resultado: {filteredStrategies.length}
        </div>
      </section>

      {loading ? (
        <div className="rounded-xl border border-white/10 bg-white/5 p-8 text-sm text-slate-300">
          Cargando estrategias...
        </div>
      ) : null}

      {error ? (
        <div className="mb-4 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      {!loading && filteredStrategies.length === 0 ? (
        <EmptyState
          title="No hay estrategias para mostrar"
          description="Todavia no se extrajeron estrategias o los filtros no tienen resultados."
        />
      ) : null}

      {!loading && filteredStrategies.length > 0 ? (
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {filteredStrategies.map((strategy) => (
            <article
              key={strategy.id}
              className="rounded-xl border border-white/10 bg-black/30 p-5"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-lg font-semibold text-white">{strategy.name}</h2>
                <StatusBadge status={strategy.evidence_strength} />
              </div>
              <p className="mt-2 text-sm text-slate-300">{strategy.description}</p>

              <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <Detail label="Type" value={strategy.strategy_type} />
                <Detail label="Market" value={strategy.market} />
                <Detail
                  label="Confidence"
                  value={`${strategy.confidence.toFixed(1)} / 10`}
                />
                <Detail label="Timeframe" value={strategy.timeframe ?? "-"} />
              </div>

              {strategy.indicators && strategy.indicators.length > 0 ? (
                <div className="mt-4">
                  <p className="text-xs uppercase tracking-wide text-slate-400">
                    Indicadores
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {strategy.indicators.map((indicator) => (
                      <span
                        key={indicator}
                        className="rounded-full border border-cyan-400/30 bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-200"
                      >
                        {indicator}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="mt-4 border-t border-white/10 pt-3 text-xs text-slate-400">
                Fuente: {strategy.source?.title ?? "Sin fuente"} (
                {strategy.source?.publication_year ?? "N/A"})
              </div>
            </article>
          ))}
        </section>
      ) : null}
    </AppShell>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-white/5 p-2.5">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-sm font-medium text-slate-100">{value}</p>
    </div>
  );
}

