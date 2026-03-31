"use client";

import { useState } from "react";
import useSWR from "swr";
import { AppShell } from "@/components/ui/AppShell";

const fetcher = async (url: string) => {
  const response = await fetch(url);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error || `HTTP ${response.status}`);
  return payload;
};

interface TradeReview {
  symbol?: string;
  pnl?: number;
  analysis?: string;
  was_correct_call?: boolean;
}

interface DailyDecision {
  date: string;
  audit: {
    overall_grade?: string;
    performance_summary?: {
      daily_pnl?: number;
      trades_closed?: number;
      wins?: number;
      losses?: number;
      win_rate?: number;
    };
    trade_reviews?: TradeReview[];
    ml_assessment?: {
      hit_rate?: number;
      recommendation?: string;
      should_enable?: boolean;
    };
    error_analysis?: string;
    market_events?: string;
    recommendations?: string[];
  } | null;
  config: {
    buy_adx_min?: number;
    buy_entropy_max?: number;
    buy_rsi_max?: number;
    sell_rsi_min?: number;
    signal_cooldown_minutes?: number;
    sl_atr_multiplier?: number;
    tp_atr_multiplier?: number;
    risk_multiplier?: number;
    max_open_positions?: number;
    quant_symbols?: string;
    reasoning?: string;
    status?: string;
  } | null;
  brief: Record<string, unknown> | null;
}

function gradeColor(grade: string): string {
  const g = grade?.toUpperCase() || "?";
  if (g === "A") return "text-emerald-400";
  if (g === "B") return "text-green-400";
  if (g === "C") return "text-yellow-400";
  if (g === "D") return "text-orange-400";
  if (g === "F") return "text-red-400";
  return "text-slate-400";
}

function pnlColor(val: number | undefined): string {
  if (val === undefined) return "text-slate-400";
  return val >= 0 ? "text-emerald-400" : "text-red-400";
}

function DayCard({ decision }: { decision: DailyDecision }) {
  const [expanded, setExpanded] = useState(false);
  const { audit, config, date } = decision;
  const perf = audit?.performance_summary;
  const grade = audit?.overall_grade || "—";

  return (
    <div className="rounded-xl border border-white/5 bg-white/[0.02] p-6 transition-all hover:border-white/10">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between text-left"
      >
        <div className="flex items-center gap-4">
          <span className="text-sm text-slate-500">{date}</span>
          <span className={`text-2xl font-bold ${gradeColor(grade)}`}>
            {grade}
          </span>
          {perf && (
            <span className={`text-lg font-mono ${pnlColor(perf.daily_pnl)}`}>
              {perf.daily_pnl !== undefined
                ? `$${perf.daily_pnl >= 0 ? "+" : ""}${Number(perf.daily_pnl).toFixed(2)}`
                : "—"}
            </span>
          )}
          {perf && perf.trades_closed !== undefined && (
            <span className="text-sm text-slate-400">
              {perf.trades_closed} trades (W:{perf.wins} L:{perf.losses})
            </span>
          )}
          {!audit && !config && (
            <span className="text-sm text-slate-500 italic">Sin datos</span>
          )}
        </div>
        <span className="text-slate-500">{expanded ? "▲" : "▼"}</span>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="mt-6 space-y-6">
          {/* Config applied */}
          {config && (
            <section>
              <h4 className="mb-2 text-sm font-semibold text-emerald-400 uppercase tracking-wide">
                Config Aplicada
              </h4>
              <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3 lg:grid-cols-5">
                <Param label="ADX min" value={config.buy_adx_min} />
                <Param label="Entropy max" value={config.buy_entropy_max} />
                <Param label="RSI max (buy)" value={config.buy_rsi_max} />
                <Param label="RSI min (sell)" value={config.sell_rsi_min} />
                <Param label="Cooldown" value={config.signal_cooldown_minutes} suffix="m" />
                <Param label="SL" value={config.sl_atr_multiplier} suffix="x ATR" />
                <Param label="TP" value={config.tp_atr_multiplier} suffix="x ATR" />
                <Param label="Risk" value={config.risk_multiplier} suffix="x" />
                <Param label="Max pos" value={config.max_open_positions} />
                <Param label="Symbols" value={config.quant_symbols} />
              </div>
              {config.reasoning && (
                <div className="mt-3 rounded-lg bg-white/[0.03] p-3">
                  <p className="text-sm text-slate-300 whitespace-pre-wrap">
                    {config.reasoning}
                  </p>
                </div>
              )}
            </section>
          )}

          {/* ML Assessment */}
          {audit?.ml_assessment && (
            <section>
              <h4 className="mb-2 text-sm font-semibold text-blue-400 uppercase tracking-wide">
                ML Assessment
              </h4>
              <div className="flex gap-4 text-sm">
                <span className="text-slate-400">
                  Hit rate: <span className="text-white font-mono">
                    {audit.ml_assessment.hit_rate !== undefined
                      ? `${(audit.ml_assessment.hit_rate * 100).toFixed(1)}%`
                      : "—"}
                  </span>
                </span>
                <span className={audit.ml_assessment.should_enable ? "text-emerald-400" : "text-red-400"}>
                  {audit.ml_assessment.recommendation || "—"}
                </span>
              </div>
            </section>
          )}

          {/* Trade Reviews */}
          {audit?.trade_reviews && audit.trade_reviews.length > 0 && (
            <section>
              <h4 className="mb-2 text-sm font-semibold text-amber-400 uppercase tracking-wide">
                Trade Reviews
              </h4>
              <div className="space-y-2">
                {audit.trade_reviews.map((t: TradeReview, i: number) => (
                  <div key={i} className="flex items-start gap-3 text-sm">
                    <span className={t.was_correct_call ? "text-emerald-400" : "text-red-400"}>
                      {t.was_correct_call ? "OK" : "XX"}
                    </span>
                    <span className="text-white font-mono w-20">{t.symbol}</span>
                    <span className={`font-mono w-16 ${pnlColor(t.pnl)}`}>
                      {t.pnl !== undefined ? `$${Number(t.pnl).toFixed(2)}` : "—"}
                    </span>
                    <span className="text-slate-400 flex-1">{t.analysis || ""}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Market Events */}
          {audit?.market_events && (
            <section>
              <h4 className="mb-2 text-sm font-semibold text-purple-400 uppercase tracking-wide">
                Eventos de Mercado
              </h4>
              <p className="text-sm text-slate-300 whitespace-pre-wrap">
                {audit.market_events}
              </p>
            </section>
          )}

          {/* Error Analysis */}
          {audit?.error_analysis && (
            <section>
              <h4 className="mb-2 text-sm font-semibold text-red-400 uppercase tracking-wide">
                Errores
              </h4>
              <p className="text-sm text-slate-300 whitespace-pre-wrap">
                {audit.error_analysis}
              </p>
            </section>
          )}

          {/* Recommendations */}
          {audit?.recommendations && audit.recommendations.length > 0 && (
            <section>
              <h4 className="mb-2 text-sm font-semibold text-cyan-400 uppercase tracking-wide">
                Recomendaciones
              </h4>
              <ul className="space-y-1 text-sm text-slate-300">
                {audit.recommendations.map((r: string, i: number) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-cyan-400">{i + 1}.</span>
                    {r}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </div>
  );
}

function Param({ label, value, suffix }: { label: string; value?: string | number; suffix?: string }) {
  if (value === undefined || value === null) return null;
  return (
    <div className="rounded bg-white/[0.03] px-2 py-1">
      <span className="text-slate-500 text-xs">{label}</span>
      <div className="text-white font-mono text-sm">
        {value}{suffix ? ` ${suffix}` : ""}
      </div>
    </div>
  );
}

export default function DailyPage() {
  const { data, error, mutate } = useSWR("/api/daily/decisions?days=30", fetcher, {
    refreshInterval: 60000,
  });
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await mutate();
    setIsRefreshing(false);
  };

  if (error) {
    return (
      <AppShell title="Daily Decisions">
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-red-300">
          <h3 className="font-semibold">Error cargando decisiones</h3>
          <p className="text-sm">{error.message}</p>
        </div>
      </AppShell>
    );
  }

  const decisions: DailyDecision[] = data?.decisions || [];

  return (
    <AppShell
      title="Daily Decisions"
      description="Decisiones diarias del LLM Analyst — auditoría, config y ML review"
      actions={
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="rounded-lg bg-emerald-500/20 px-4 py-2 text-sm text-emerald-400 transition-colors hover:bg-emerald-500/30 disabled:opacity-50"
        >
          {isRefreshing ? "..." : "Refresh"}
        </button>
      }
    >
      <div className="space-y-4">
          {!data && (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-20 animate-pulse rounded-xl bg-white/[0.03]" />
              ))}
            </div>
          )}

          {decisions.length === 0 && data && (
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-12 text-center">
              <p className="text-lg text-slate-400">
                No hay decisiones diarias todavia
              </p>
              <p className="mt-2 text-sm text-slate-500">
                El analyst corre automaticamente a las 03:00-04:00 UTC cada dia.
                <br />
                Las decisiones apareceran aca despues de la primera ejecucion.
              </p>
            </div>
          )}

          {decisions.map((d) => (
            <DayCard key={d.date} decision={d} />
          ))}
      </div>
    </AppShell>
  );
}
