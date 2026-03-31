"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import useSWR from "swr";
import { AppShell } from "@/components/ui/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { ChartPoint } from "@/components/portfolio/PnlChart";

// Calculado al cargar el módulo (una sola vez, fuera del ciclo de render)
function buildCutoffs(): Record<string, string> {
  const d7 = new Date();
  d7.setDate(d7.getDate() - 7);
  const d30 = new Date();
  d30.setDate(d30.getDate() - 30);
  return {
    "7d": d7.toISOString().slice(0, 10),
    "30d": d30.toISOString().slice(0, 10),
  };
}
const PERIOD_CUTOFFS = buildCutoffs();

// Cargamos el gráfico solo en el cliente (Recharts no soporta SSR)
const PnlChart = dynamic(() => import("@/components/portfolio/PnlChart"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[220px] items-center justify-center">
      <div className="h-5 w-5 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
    </div>
  ),
});

const fetcher = async (url: string) => {
  const res = await fetch(url);
  const body = await res.json();
  if (!res.ok) throw new Error(body?.details || body?.error || `HTTP ${res.status}`);
  return body;
};

// ── Tooltip educativo ─────────────────────────────────────────────────────────

function MetricInfo({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative ml-1 inline-block">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-slate-600 text-[10px] font-bold text-slate-500 transition-colors hover:border-slate-400 hover:text-slate-300"
        aria-label="Explicación de la métrica"
      >
        ?
      </button>
      {open && (
        <span className="absolute bottom-full left-1/2 z-50 mb-2 w-56 -translate-x-1/2 rounded-lg border border-white/10 bg-slate-800 p-2.5 text-left text-xs leading-relaxed text-slate-300 shadow-xl">
          {text}
          <span
            className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800"
          />
        </span>
      )}
    </span>
  );
}

// ── Panel de estado: Hoy / Semana / Mes ──────────────────────────────────────

type PeriodData = { pnl: number; trades: number; wins: number };

function StatusCard({
  label,
  period,
}: {
  label: string;
  period: PeriodData | undefined;
}) {
  const pnl = period?.pnl ?? 0;
  const trades = period?.trades ?? 0;
  const wins = period?.wins ?? 0;
  const winRate = trades > 0 ? Math.round((wins / trades) * 100) : null;

  const isPositive = pnl > 0;
  const isNegative = pnl < 0;

  const borderColor = isPositive
    ? "border-emerald-500/30"
    : isNegative
    ? "border-red-500/30"
    : "border-white/10";

  const pnlColor = isPositive
    ? "text-emerald-400"
    : isNegative
    ? "text-red-400"
    : "text-slate-400";

  const dotColor = isPositive
    ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"
    : isNegative
    ? "bg-red-500"
    : "bg-slate-600";

  return (
    <div
      className={`rounded-xl border ${borderColor} bg-slate-900/50 p-5 backdrop-blur-xl`}
    >
      <div className="mb-3 flex items-center gap-2">
        <div className={`h-2 w-2 rounded-full ${dotColor}`} />
        <span className="text-xs font-medium text-slate-400">{label}</span>
      </div>
      <p className={`font-mono text-2xl font-bold ${pnlColor}`}>
        {pnl >= 0 ? "+" : ""}${Math.abs(pnl).toFixed(2)}
      </p>
      <div className="mt-2 flex gap-3 text-xs text-slate-500">
        <span>{trades} trades</span>
        {winRate !== null && <span>{winRate}% wins</span>}
      </div>
    </div>
  );
}

// ── Página principal ─────────────────────────────────────────────────────────

export default function PortfolioPage() {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [chartPeriod, setChartPeriod] = useState<"7d" | "30d" | "all">("30d");

  const {
    data: portfolio,
    error: portfolioError,
    mutate,
  } = useSWR("/api/portfolio", fetcher, { refreshInterval: 30_000 });

  const { data: chartData } = useSWR("/api/portfolio/pnl-chart", fetcher, {
    refreshInterval: 60_000,
  });

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await mutate();
    setIsRefreshing(false);
  };

  // ── Loading ─────────────────────────────────────────────────────────────
  if (!portfolio && !portfolioError) {
    return (
      <AppShell>
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-28 animate-pulse rounded-xl bg-slate-800/50" />
            ))}
          </div>
          <div className="h-72 animate-pulse rounded-xl bg-slate-800/50" />
          <div className="grid grid-cols-2 gap-4">
            <div className="h-40 animate-pulse rounded-xl bg-slate-800/50" />
            <div className="h-40 animate-pulse rounded-xl bg-slate-800/50" />
          </div>
        </div>
      </AppShell>
    );
  }

  // ── Error ───────────────────────────────────────────────────────────────
  if (portfolioError) {
    return (
      <AppShell>
        <div className="rounded-xl border border-red-500/20 bg-red-900/10 p-6">
          <p className="font-semibold text-red-400">Error cargando portfolio</p>
          <p className="mt-1 text-sm text-slate-400">{portfolioError.message}</p>
        </div>
      </AppShell>
    );
  }

  const balance = portfolio?.balance ?? { total: 0, available: 0, inPositions: 0, locked: 0 };
  const positions = portfolio?.positions ?? { open: [], openCount: 0, totalValue: 0 };
  const pnl = portfolio?.pnl ?? {
    daily: { realized: 0, unrealized: 0, total: 0 },
    allTime: { realized: 0, unrealized: 0, total: 0 },
  };
  const perf = portfolio?.performance ?? {
    totalTrades: 0,
    winningTrades: 0,
    losingTrades: 0,
    winRate: "0.00",
    avgWin: "0.00",
  };
  const risk = portfolio?.risk ?? {
    currentDrawdown: 0,
    currentDrawdownPercent: "0.00",
    maxDrawdown: 0,
    maxDrawdownPercent: 0,
    peakBalance: 0,
    unresolvedRiskEvents: 0,
  };

  const pnlSeries: ChartPoint[] = chartData?.chartData ?? [];
  const periods = chartData?.periods ?? {};

  return (
    <AppShell
      title="Portfolio"
      description="Rendimiento de trading en tiempo real"
      actions={
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="rounded-lg border border-white/10 bg-slate-800 px-4 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-700 hover:text-white disabled:opacity-50"
        >
          {isRefreshing ? "Actualizando..." : "Actualizar"}
        </button>
      }
    >
      <div className="space-y-6">
        {/* ── 1. Panel de Estado ────────────────────────────────────────── */}
        <section>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">
            ¿Cómo voy?
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatusCard label="Hoy" period={periods.today} />
            <StatusCard label="Esta semana" period={periods.week} />
            <StatusCard label="Este mes" period={periods.month} />
          </div>
        </section>

        {/* ── 2. Gráfico PnL Acumulado ──────────────────────────────────── */}
        <section className="rounded-xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-white">
                PnL Acumulado
                <MetricInfo text="Muestra cómo creció (o bajó) tu capital desde el primer trade hasta hoy. Una línea que sube = estás ganando dinero de forma consistente." />
              </h2>
              <p className="mt-0.5 text-xs text-slate-500">
                Ganancia o pérdida total de todos tus trades cerrados
              </p>
            </div>
            <div className="flex gap-1">
              {(["7d", "30d", "all"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setChartPeriod(p)}
                  className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                    chartPeriod === p
                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                      : "text-slate-500 hover:text-slate-300 border border-transparent"
                  }`}
                >
                  {p === "all" ? "Todo" : p.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <PnlChart
            data={pnlSeries}
            cutoffIso={chartPeriod === "all" ? null : (PERIOD_CUTOFFS[chartPeriod] ?? null)}
          />
        </section>

        {/* ── 3. Balance ───────────────────────────────────────────────── */}
        <section>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">
            Balance
          </h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-xl border border-white/10 bg-slate-900/50 p-5 backdrop-blur-xl">
              <p className="text-xs text-slate-500">
                Total
                <MetricInfo text="Todo tu dinero: el que está libre + el que está en trades abiertos." />
              </p>
              <p className="mt-2 font-mono text-2xl font-bold text-white">
                ${balance.total.toLocaleString()}
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-900/50 p-5 backdrop-blur-xl">
              <p className="text-xs text-slate-500">
                Disponible
                <MetricInfo text="Dinero libre para abrir nuevas posiciones. No está comprometido en ningún trade." />
              </p>
              <p className="mt-2 font-mono text-2xl font-bold text-emerald-400">
                ${balance.available.toLocaleString()}
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-900/50 p-5 backdrop-blur-xl">
              <p className="text-xs text-slate-500">
                En posiciones
                <MetricInfo text="Cuánto dinero está actualmente en trades abiertos (todavía no cerrados)." />
              </p>
              <p className="mt-2 font-mono text-2xl font-bold text-blue-400">
                ${balance.inPositions.toLocaleString()}
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-900/50 p-5 backdrop-blur-xl">
              <p className="text-xs text-slate-500">
                Bloqueado
                <MetricInfo text="Monto reservado como garantía (margen) o en órdenes pendientes." />
              </p>
              <p className="mt-2 font-mono text-2xl font-bold text-slate-400">
                ${balance.locked.toLocaleString()}
              </p>
            </div>
          </div>
        </section>

        {/* ── 4. P&L Desglosado ────────────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {/* Daily */}
          <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl">
            <h3 className="mb-4 text-sm font-semibold text-white">
              P&L de Hoy
              <MetricInfo text="P&L = Profit and Loss = Ganancia y Pérdida. Cuánto ganaste o perdiste sólo en el día de hoy." />
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">
                  Realizado
                  <MetricInfo text="Ganancia/pérdida de trades YA cerrados. Este dinero ya es tuyo (o perdido definitivamente)." />
                </span>
                <span
                  className={`font-mono text-sm font-semibold ${
                    pnl.daily.realized >= 0 ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  {pnl.daily.realized >= 0 ? "+" : ""}${pnl.daily.realized.toFixed(2)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">
                  No realizado
                  <MetricInfo text="Ganancia/pérdida de trades AÚN ABIERTOS. Puede cambiar hasta que cierres la posición." />
                </span>
                <span
                  className={`font-mono text-sm font-semibold ${
                    pnl.daily.unrealized >= 0 ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  {pnl.daily.unrealized >= 0 ? "+" : ""}${pnl.daily.unrealized.toFixed(2)}
                </span>
              </div>
              <div className="border-t border-white/5 pt-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-white">Total</span>
                  <span
                    className={`font-mono text-lg font-bold ${
                      pnl.daily.total >= 0 ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    {pnl.daily.total >= 0 ? "+" : ""}${pnl.daily.total.toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* All-Time */}
          <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl">
            <h3 className="mb-4 text-sm font-semibold text-white">
              P&L Histórico
              <MetricInfo text="El P&L total desde que empezó el bot. Es el resumen de TODOS los trades que hizo hasta ahora." />
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">
                  Realizado
                  <MetricInfo text="Suma de todas las ganancias y pérdidas de trades cerrados en la historia completa." />
                </span>
                <span
                  className={`font-mono text-sm font-semibold ${
                    pnl.allTime.realized >= 0 ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  {pnl.allTime.realized >= 0 ? "+" : ""}${pnl.allTime.realized.toFixed(2)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">
                  No realizado
                  <MetricInfo text="Ganancia/pérdida latente de todas las posiciones abiertas ahora mismo." />
                </span>
                <span
                  className={`font-mono text-sm font-semibold ${
                    pnl.allTime.unrealized >= 0 ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  {pnl.allTime.unrealized >= 0 ? "+" : ""}${pnl.allTime.unrealized.toFixed(2)}
                </span>
              </div>
              <div className="border-t border-white/5 pt-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-white">Total</span>
                  <span
                    className={`font-mono text-lg font-bold ${
                      pnl.allTime.total >= 0 ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    {pnl.allTime.total >= 0 ? "+" : ""}${pnl.allTime.total.toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── 5. Estadísticas de rendimiento ───────────────────────────── */}
        <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl">
          <h3 className="mb-4 text-sm font-semibold text-white">Estadísticas</h3>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
            <div>
              <p className="text-xs text-slate-500">
                Trades totales
                <MetricInfo text="Cantidad de operaciones cerradas desde el inicio. Más trades = más experiencia para el algoritmo." />
              </p>
              <p className="mt-1.5 font-mono text-2xl font-bold text-white">
                {perf.totalTrades}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">
                Ganadores
                <MetricInfo text="Trades que terminaron con ganancia (PnL positivo)." />
              </p>
              <p className="mt-1.5 font-mono text-2xl font-bold text-emerald-400">
                {perf.winningTrades}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">
                Perdedores
                <MetricInfo text="Trades que terminaron con pérdida (PnL negativo). Tener algunos perdedores es normal y esperado." />
              </p>
              <p className="mt-1.5 font-mono text-2xl font-bold text-red-400">
                {perf.losingTrades}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">
                Win rate
                <MetricInfo text="% de trades que ganaron. Ej: 60% significa que 6 de cada 10 trades terminaron en verde. Arriba del 50% es buena señal, pero no es todo." />
              </p>
              <p className="mt-1.5 font-mono text-2xl font-bold text-blue-400">
                {perf.winRate}%
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">
                Ganancia prom.
                <MetricInfo text="En promedio, cuánto gana cada trade ganador. Comparalo con el promedio de pérdida para ver si el bot es rentable." />
              </p>
              <p className="mt-1.5 font-mono text-2xl font-bold text-emerald-400">
                ${perf.avgWin}
              </p>
            </div>
          </div>
        </div>

        {/* ── 6. Posiciones abiertas ────────────────────────────────────── */}
        <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">
              Posiciones abiertas
              <MetricInfo text="Trades que el bot abrió y todavía no cerró. Su PnL cambia en tiempo real según el precio de mercado." />
            </h3>
            <span className="rounded-full bg-slate-800 px-3 py-0.5 text-xs font-medium text-slate-400">
              {positions.openCount} activas · ${positions.totalValue.toFixed(2)} invertido
            </span>
          </div>

          {positions.open.length === 0 ? (
            <div className="rounded-lg border border-dashed border-white/10 py-8 text-center">
              <p className="text-sm text-slate-500">Sin posiciones abiertas</p>
              <p className="mt-1 text-xs text-slate-600">
                El bot esperará la próxima señal de entrada
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr className="border-b border-white/5">
                    {["Par", "Lado", "Entrada", "Precio actual", "Cantidad", "P&L"].map(
                      (h) => (
                        <th
                          key={h}
                          className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-slate-500 last:text-right"
                        >
                          {h}
                        </th>
                      )
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {positions.open.map((pos: any) => (
                    <tr key={pos.id} className="transition-colors hover:bg-white/2">
                      <td className="whitespace-nowrap px-3 py-3 text-sm font-mono font-medium text-white">
                        {pos.symbol}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-sm">
                        <StatusBadge
                          status={pos.side}
                          variant={pos.side === "long" ? "success" : "warning"}
                        />
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-right font-mono text-sm text-slate-300">
                        ${Number(pos.entry_price ?? 0).toLocaleString()}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-right font-mono text-sm text-slate-300">
                        ${Number(pos.current_price ?? 0).toLocaleString()}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-right font-mono text-sm text-slate-300">
                        {Number(pos.current_quantity ?? 0)}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-right">
                        <span
                          className={`font-mono text-sm font-semibold ${
                            Number(pos.unrealized_pnl ?? 0) >= 0
                              ? "text-emerald-400"
                              : "text-red-400"
                          }`}
                        >
                          {Number(pos.unrealized_pnl ?? 0) >= 0 ? "+" : ""}$
                          {Number(pos.unrealized_pnl ?? 0).toFixed(2)}
                        </span>
                        <span
                          className={`ml-1 text-xs ${
                            Number(pos.unrealized_pnl_percent ?? 0) >= 0
                              ? "text-emerald-600"
                              : "text-red-600"
                          }`}
                        >
                          ({Number(pos.unrealized_pnl_percent ?? 0) >= 0 ? "+" : ""}
                          {Number(pos.unrealized_pnl_percent ?? 0).toFixed(2)}%)
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── 7. Métricas de riesgo ─────────────────────────────────────── */}
        <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl">
          <h3 className="mb-4 text-sm font-semibold text-white">Riesgo</h3>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <p className="text-xs text-slate-500">
                Drawdown actual
                <MetricInfo text="Cuánto bajó tu capital desde su punto más alto hasta ahora. Es la 'pérdida temporaria' en curso. Si es 0, estás en máximos." />
              </p>
              <p className="mt-1.5 font-mono text-2xl font-bold text-red-400">
                ${risk.currentDrawdown.toFixed(2)}
              </p>
              <p className="text-xs text-slate-600">({risk.currentDrawdownPercent}%)</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">
                Drawdown máximo
                <MetricInfo text="La mayor caída histórica de tu capital (de pico a valle). Cuanto menor, mejor. Te dice cuánto riesgo tuvo el bot en su peor momento." />
              </p>
              <p className="mt-1.5 font-mono text-2xl font-bold text-red-500">
                ${risk.maxDrawdown.toFixed(2)}
              </p>
              <p className="text-xs text-slate-600">({risk.maxDrawdownPercent}%)</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">
                Balance pico
                <MetricInfo text="El mayor saldo que llegaste a tener. El drawdown se calcula como la distancia entre este valor y el balance actual." />
              </p>
              <p className="mt-1.5 font-mono text-2xl font-bold text-white">
                ${risk.peakBalance.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">
                Alertas activas
                <MetricInfo text="Eventos de riesgo que el bot detectó y no fueron resueltos. Conviene revisarlos en la sección History." />
              </p>
              <p
                className={`mt-1.5 font-mono text-2xl font-bold ${
                  risk.unresolvedRiskEvents > 0 ? "text-amber-400" : "text-slate-400"
                }`}
              >
                {risk.unresolvedRiskEvents}
              </p>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
