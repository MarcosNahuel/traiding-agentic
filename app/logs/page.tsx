"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/ui/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";

interface HealthResponse {
  status: string;
  timestamp: string;
}

interface DiagnosticResponse {
  status: string;
  timestamp: string;
  nodeEnv?: string;
  variables?: Record<string, { exists: boolean; length?: number }>;
}

interface SourceRecord {
  id: string;
  title: string | null;
  status: string;
  updated_at: string;
}

interface SourcesResponse {
  sources: SourceRecord[];
}

interface StrategiesResponse {
  strategies: unknown[];
}

interface GuidesResponse {
  guides?: unknown[];
  guide?: unknown;
}

interface AgentLog {
  id: string;
  agent_name: string;
  action: string;
  status: string;
  created_at: string;
  output_summary: string | null;
}

interface LogsResponse {
  logs: AgentLog[];
}

export default function LogsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [diagnostic, setDiagnostic] = useState<DiagnosticResponse | null>(null);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [strategiesCount, setStrategiesCount] = useState(0);
  const [guidesCount, setGuidesCount] = useState(0);
  const [agentLogs, setAgentLogs] = useState<AgentLog[]>([]);
  const [logsEndpointStatus, setLogsEndpointStatus] = useState<
    "ok" | "missing" | "error"
  >("missing");

  const load = async () => {
    setLoading(true);
    setError(null);

    try {
      const [
        healthRes,
        diagnosticRes,
        sourcesRes,
        strategiesRes,
        guidesRes,
        logsRes,
      ] = await Promise.all([
        fetch("/api/health", { cache: "no-store" }),
        fetch("/api/diagnostic", { cache: "no-store" }),
        fetch("/api/sources?limit=20", { cache: "no-store" }),
        fetch("/api/strategies", { cache: "no-store" }),
        fetch("/api/guides", { cache: "no-store" }),
        fetch("/api/logs?limit=20", { cache: "no-store" }),
      ]);

      if (healthRes.ok) {
        setHealth((await healthRes.json()) as HealthResponse);
      }

      if (diagnosticRes.ok) {
        setDiagnostic((await diagnosticRes.json()) as DiagnosticResponse);
      }

      if (sourcesRes.ok) {
        const payload = (await sourcesRes.json()) as SourcesResponse;
        setSources(payload.sources ?? []);
      }

      if (strategiesRes.ok) {
        const payload = (await strategiesRes.json()) as StrategiesResponse;
        setStrategiesCount(payload.strategies?.length ?? 0);
      }

      if (guidesRes.ok) {
        const payload = (await guidesRes.json()) as GuidesResponse;
        if (payload.guides) {
          setGuidesCount(payload.guides.length);
        } else if (payload.guide) {
          setGuidesCount(1);
        } else {
          setGuidesCount(0);
        }
      }

      if (logsRes.ok) {
        const payload = (await logsRes.json()) as LogsResponse;
        setAgentLogs(payload.logs ?? []);
        setLogsEndpointStatus("ok");
      } else if (logsRes.status === 404) {
        setLogsEndpointStatus("missing");
        setAgentLogs([]);
      } else {
        setLogsEndpointStatus("error");
        setAgentLogs([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error inesperado");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const sourceCounters = useMemo(() => {
    const map: Record<string, number> = {};
    for (const source of sources) {
      map[source.status] = (map[source.status] ?? 0) + 1;
    }
    return map;
  }, [sources]);

  return (
    <AppShell
      title="Logs & Monitoring"
      description="Vista operativa del sistema usando endpoints disponibles en frontend."
      actions={
        <button
          onClick={() => void load()}
          className="rounded-md border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10"
        >
          Refrescar
        </button>
      }
    >
      {error ? (
        <div className="mb-4 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      <section className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-4">
        <Metric title="Health" value={health?.status ?? "-"} />
        <Metric title="Sources" value={String(sources.length)} />
        <Metric title="Strategies" value={String(strategiesCount)} />
        <Metric title="Guides" value={String(guidesCount)} />
      </section>

      <section className="mb-4 rounded-xl border border-white/10 bg-black/30 p-4">
        <h2 className="text-sm uppercase tracking-wide text-slate-300">
          Estado de endpoints
        </h2>
        <div className="mt-3 flex flex-wrap gap-3 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-slate-300">/api/health</span>
            <StatusBadge status={health ? "success" : "error"} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-300">/api/diagnostic</span>
            <StatusBadge status={diagnostic ? "success" : "error"} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-300">/api/logs</span>
            <StatusBadge
              status={
                logsEndpointStatus === "ok"
                  ? "success"
                  : logsEndpointStatus === "missing"
                    ? "warning"
                    : "error"
              }
            />
          </div>
        </div>
        {logsEndpointStatus === "missing" ? (
          <p className="mt-3 rounded-md border border-amber-400/30 bg-amber-500/10 p-3 text-sm text-amber-200">
            El endpoint /api/logs no existe todavia. Se muestran metricas base
            y actividad derivada de /api/sources.
          </p>
        ) : null}
      </section>

      <section className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-white/10 bg-black/30 p-4">
          <h2 className="text-sm uppercase tracking-wide text-slate-300">
            Sources por estado
          </h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {Object.keys(sourceCounters).length === 0 ? (
              <span className="text-sm text-slate-400">Sin datos.</span>
            ) : (
              Object.entries(sourceCounters).map(([status, count]) => (
                <div
                  key={status}
                  className="rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                >
                  {status}: {count}
                </div>
              ))
            )}
          </div>
        </div>

        <div className="rounded-xl border border-white/10 bg-black/30 p-4">
          <h2 className="text-sm uppercase tracking-wide text-slate-300">
            Diagnostico de variables
          </h2>
          <ul className="mt-3 space-y-2 text-sm">
            {diagnostic?.variables ? (
              Object.entries(diagnostic.variables).map(([name, details]) => (
                <li key={name} className="flex items-center justify-between gap-3">
                  <span className="text-slate-300">{name}</span>
                  <StatusBadge status={details.exists ? "success" : "error"} />
                </li>
              ))
            ) : (
              <li className="text-slate-400">Sin datos de diagnostico.</li>
            )}
          </ul>
        </div>
      </section>

      <section className="rounded-xl border border-white/10 bg-black/30 p-4">
        <h2 className="text-sm uppercase tracking-wide text-slate-300">
          Actividad reciente
        </h2>
        {loading ? (
          <p className="mt-3 text-sm text-slate-300">Cargando actividad...</p>
        ) : null}

        {!loading && logsEndpointStatus === "ok" && agentLogs.length === 0 ? (
          <EmptyState
            title="No hay logs"
            description="El endpoint existe pero no devolvio eventos."
          />
        ) : null}

        {!loading && logsEndpointStatus === "ok" && agentLogs.length > 0 ? (
          <ul className="mt-3 space-y-2">
            {agentLogs.map((log) => (
              <li
                key={log.id}
                className="rounded-md border border-white/10 bg-white/5 p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium text-white">
                    {log.agent_name} - {log.action}
                  </p>
                  <StatusBadge status={log.status} />
                </div>
                <p className="mt-1 text-xs text-slate-300">
                  {new Date(log.created_at).toLocaleString()}
                </p>
                {log.output_summary ? (
                  <p className="mt-1 text-sm text-slate-200">{log.output_summary}</p>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}

        {!loading && logsEndpointStatus !== "ok" && sources.length > 0 ? (
          <ul className="mt-3 space-y-2">
            {sources.slice(0, 10).map((source) => (
              <li
                key={source.id}
                className="rounded-md border border-white/10 bg-white/5 p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium text-white">
                    {source.title ?? "Sin titulo"}
                  </p>
                  <StatusBadge status={source.status} />
                </div>
                <p className="mt-1 text-xs text-slate-300">
                  {new Date(source.updated_at).toLocaleString()}
                </p>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </AppShell>
  );
}

function Metric({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{title}</p>
      <p className="mt-1 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

