"use client";

import { useState } from "react";
import useSWR from "swr";
import { AppShell } from "@/components/ui/AppShell";

const SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"];
const STRATEGIES = ["sma_cross", "rsi_reversal", "bbands_squeeze"];
const INTERVALS = ["15m", "1h", "4h", "1d"];

const fetcher = (url: string) => fetch(url).then((r) => r.json());

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return "—";
  return n.toFixed(decimals);
}

function pct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

// ─── Engine Status Card ───────────────────────────────────────────────────────

function EngineStatusCard({ status }: { status: any }) {
  if (!status) {
    return (
      <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6 animate-pulse">
        <div className="h-5 w-40 rounded bg-slate-700" />
      </div>
    );
  }

  const moduleEntries = Object.entries(status.modules ?? {}) as [string, any][];

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Engine Status</h2>
        <div className="flex items-center gap-2">
          <div
            className={`h-2 w-2 rounded-full ${
              status.enabled ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-red-500"
            }`}
          />
          <span className="text-xs text-slate-400">
            {status.enabled ? "Active" : "Disabled"}
          </span>
        </div>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <p className="text-xs text-slate-500">Tick Count</p>
          <p className="mt-1 text-2xl font-bold text-white">{status.tick_count ?? 0}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Primary Interval</p>
          <p className="mt-1 text-xl font-bold text-emerald-400">{status.primary_interval ?? "—"}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Symbols</p>
          <p className="mt-1 text-sm font-medium text-white">{(status.symbols ?? []).length} pairs</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Last Tick</p>
          <p className="mt-1 text-xs text-slate-400">
            {status.last_tick_at
              ? new Date(status.last_tick_at).toLocaleTimeString()
              : "Never"}
          </p>
        </div>
      </div>

      {/* Modules grid */}
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {moduleEntries.map(([name, mod]) => (
          <div
            key={name}
            className="flex items-center gap-2 rounded-lg border border-white/5 bg-white/5 px-3 py-2"
          >
            <div
              className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                mod?.status === "active" ? "bg-emerald-500" : "bg-red-400"
              }`}
            />
            <span className="truncate text-xs text-slate-300">
              {name.replace(/_/g, " ")}
            </span>
          </div>
        ))}
      </div>

      {/* Errors */}
      {status.errors && status.errors.length > 0 && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3">
          <p className="mb-1 text-xs font-medium text-red-400">Recent Errors</p>
          {status.errors.slice(0, 3).map((e: string, i: number) => (
            <p key={i} className="text-xs text-red-300/80">
              {e}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Market Analysis Card ────────────────────────────────────────────────────

function AnalysisCard({
  symbol,
  analysis,
  loading,
}: {
  symbol: string;
  analysis: any;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-20 rounded-xl bg-slate-800" />
        <div className="h-40 rounded-xl bg-slate-800" />
      </div>
    );
  }
  if (!analysis || analysis.error) {
    return (
      <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6 text-center text-slate-500">
        {analysis?.error ?? `No data for ${symbol}`}
      </div>
    );
  }

  const { indicators: ind, entropy, regime, sr_levels, position_sizing, is_tradable, trade_blocks } = analysis;
  const levels = sr_levels?.levels ?? [];
  const supports = levels.filter((l: any) => l.level_type === "support").slice(0, 3);
  const resistances = levels.filter((l: any) => l.level_type === "resistance").slice(0, 3);

  const regimeColor: Record<string, string> = {
    trending_up: "text-emerald-400",
    trending_down: "text-red-400",
    ranging: "text-yellow-400",
    volatile: "text-orange-400",
    low_liquidity: "text-slate-400",
  };

  return (
    <div className="space-y-4">
      {/* Tradability banner */}
      <div
        className={`flex items-center justify-between rounded-xl border px-5 py-4 ${
          is_tradable
            ? "border-emerald-500/30 bg-emerald-500/10"
            : "border-red-500/30 bg-red-500/10"
        }`}
      >
        <div className="flex items-center gap-3">
          <div
            className={`h-3 w-3 rounded-full ${
              is_tradable ? "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.6)]" : "bg-red-400"
            }`}
          />
          <span className={`font-semibold ${is_tradable ? "text-emerald-300" : "text-red-300"}`}>
            {is_tradable ? "Tradable" : "Blocked"}
          </span>
        </div>
        {!is_tradable && trade_blocks?.length > 0 && (
          <div className="text-right">
            {trade_blocks.map((b: string, i: number) => (
              <p key={i} className="text-xs text-red-400">
                {b}
              </p>
            ))}
          </div>
        )}
        {regime && (
          <span className={`text-sm font-medium ${regimeColor[regime.regime] ?? "text-slate-400"}`}>
            {regime.regime?.replace(/_/g, " ")} ({fmt(regime.confidence, 0)}%)
          </span>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Indicators */}
        <div className="rounded-xl border border-white/10 bg-slate-900/50 p-5">
          <h3 className="mb-3 text-sm font-semibold text-slate-300">Technical Indicators</h3>
          <div className="space-y-2 text-xs">
            {[
              ["RSI (14)", fmt(ind?.rsi_14), ind?.rsi_14 > 70 ? "text-red-400" : ind?.rsi_14 < 30 ? "text-emerald-400" : "text-white"],
              ["ADX (14)", fmt(ind?.adx_14), ind?.adx_14 > 25 ? "text-emerald-400" : "text-yellow-400"],
              ["MACD Hist", fmt(ind?.macd_histogram), (ind?.macd_histogram ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"],
              ["ATR (14)", fmt(ind?.atr_14), "text-white"],
              ["BB Width", fmt(ind?.bb_bandwidth, 4), "text-slate-300"],
            ].map(([label, value, color]) => (
              <div key={label as string} className="flex justify-between">
                <span className="text-slate-500">{label}</span>
                <span className={color as string}>{value as string}</span>
              </div>
            ))}
            {/* SMA trend */}
            {ind?.sma_200 && (
              <div className="flex justify-between">
                <span className="text-slate-500">vs SMA 200</span>
                <span className={ind?.sma_20 > ind?.sma_200 ? "text-emerald-400" : "text-red-400"}>
                  {ind?.sma_20 > ind?.sma_200 ? "▲ Above" : "▼ Below"}
                </span>
              </div>
            )}
          </div>

          {/* Entropy bar */}
          {entropy && (
            <div className="mt-4">
              <div className="mb-1 flex justify-between text-xs">
                <span className="text-slate-500">Entropy Ratio</span>
                <span className={entropy.entropy_ratio > 0.85 ? "text-red-400" : "text-emerald-400"}>
                  {fmt(entropy.entropy_ratio, 3)} / 0.85
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-700">
                <div
                  className={`h-full rounded-full transition-all ${
                    entropy.entropy_ratio > 0.85 ? "bg-red-400" : "bg-emerald-400"
                  }`}
                  style={{ width: `${Math.min(entropy.entropy_ratio * 100, 100)}%` }}
                />
              </div>
            </div>
          )}

          {/* Hurst */}
          {regime?.hurst_exponent != null && (
            <div className="mt-3 flex justify-between text-xs">
              <span className="text-slate-500">Hurst Exponent</span>
              <span className={regime.hurst_exponent > 0.55 ? "text-emerald-400" : regime.hurst_exponent < 0.45 ? "text-blue-400" : "text-slate-300"}>
                {fmt(regime.hurst_exponent, 3)}{" "}
                {regime.hurst_exponent > 0.55 ? "(trending)" : regime.hurst_exponent < 0.45 ? "(mean-rev)" : "(random)"}
              </span>
            </div>
          )}
        </div>

        {/* S/R Levels + Sizing */}
        <div className="space-y-4">
          <div className="rounded-xl border border-white/10 bg-slate-900/50 p-5">
            <h3 className="mb-3 text-sm font-semibold text-slate-300">Support / Resistance</h3>
            <div className="space-y-1 text-xs">
              {resistances.map((l: any, i: number) => (
                <div key={i} className="flex justify-between">
                  <span className="text-red-400">R{i + 1}</span>
                  <span className="text-white">${l.price_level?.toLocaleString()}</span>
                  <span className="text-slate-500">{fmt(l.distance_pct, 1)}%</span>
                  <span className="text-slate-600">str {fmt(l.strength, 2)}</span>
                </div>
              ))}
              {supports.map((l: any, i: number) => (
                <div key={i} className="flex justify-between">
                  <span className="text-emerald-400">S{i + 1}</span>
                  <span className="text-white">${l.price_level?.toLocaleString()}</span>
                  <span className="text-slate-500">{fmt(l.distance_pct, 1)}%</span>
                  <span className="text-slate-600">str {fmt(l.strength, 2)}</span>
                </div>
              ))}
              {levels.length === 0 && (
                <p className="text-slate-600">No levels computed yet</p>
              )}
            </div>
          </div>

          {position_sizing && (
            <div className="rounded-xl border border-white/10 bg-slate-900/50 p-5">
              <h3 className="mb-3 text-sm font-semibold text-slate-300">Position Sizing</h3>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Recommended</span>
                  <span className="text-lg font-bold text-emerald-400">
                    ${fmt(position_sizing.recommended_size_usd, 0)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Method</span>
                  <span className="text-white">{position_sizing.method}</span>
                </div>
                {position_sizing.kelly_fraction != null && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Kelly f*</span>
                    <span className="text-white">{pct(position_sizing.kelly_fraction)}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Performance Metrics Card ────────────────────────────────────────────────

function PerformanceCard({ perfData }: { perfData: any }) {
  const metrics: any[] = perfData?.metrics ?? [];
  const byType: Record<string, any> = {};
  for (const m of metrics) byType[m.metric_type] = m;

  const rows: [string, string][] = [
    ["Sharpe Ratio", "sharpe_ratio"],
    ["Sortino Ratio", "sortino_ratio"],
    ["Calmar Ratio", "calmar_ratio"],
    ["Win Rate", "win_rate"],
    ["Profit Factor", "profit_factor"],
    ["Kelly Fraction", "kelly_fraction"],
    ["Total Trades", "total_trades"],
    ["Max Drawdown $", "max_drawdown"],
  ];

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6">
      <h2 className="mb-4 text-lg font-semibold text-white">Performance Metrics</h2>
      {metrics.length === 0 ? (
        <p className="text-sm text-slate-500">
          No data yet — metrics are computed every 6 hours (360 ticks) from closed positions.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/5">
                <th className="py-2 text-left font-medium text-slate-500">Metric</th>
                <th className="py-2 text-right font-medium text-emerald-400">All Time</th>
                <th className="py-2 text-right font-medium text-blue-400">30 Days</th>
                <th className="py-2 text-right font-medium text-violet-400">7 Days</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([label, key]) => (
                <tr key={key} className="border-b border-white/5">
                  <td className="py-2 text-slate-400">{label}</td>
                  {["all_time", "rolling_30d", "rolling_7d"].map((t) => {
                    const val = byType[t]?.[key];
                    const display =
                      key === "win_rate" || key === "kelly_fraction"
                        ? pct(val)
                        : key === "total_trades"
                        ? val ?? "—"
                        : fmt(val);
                    return (
                      <td key={t} className="py-2 text-right text-white">
                        {display}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Backtest Card ───────────────────────────────────────────────────────────

function BacktestCard({ backtestData, onRun }: { backtestData: any; onRun: () => void }) {
  const [form, setForm] = useState({
    strategy_id: "sma_cross",
    symbol: "BTCUSDT",
    interval: "1h",
    lookback_days: 30,
  });
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch("/api/quant/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.error ?? "Backtest failed");
      } else {
        onRun();
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  };

  const results: any[] = backtestData?.results ?? [];

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6">
      <h2 className="mb-4 text-lg font-semibold text-white">Backtesting</h2>

      {/* Form */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div>
          <label className="mb-1 block text-xs text-slate-500">Strategy</label>
          <select
            value={form.strategy_id}
            onChange={(e) => setForm((f) => ({ ...f, strategy_id: e.target.value }))}
            className="w-full rounded-lg border border-white/10 bg-slate-800 px-3 py-1.5 text-xs text-white focus:border-emerald-500/50 focus:outline-none"
          >
            {STRATEGIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-500">Symbol</label>
          <select
            value={form.symbol}
            onChange={(e) => setForm((f) => ({ ...f, symbol: e.target.value }))}
            className="w-full rounded-lg border border-white/10 bg-slate-800 px-3 py-1.5 text-xs text-white focus:border-emerald-500/50 focus:outline-none"
          >
            {SYMBOLS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-500">Interval</label>
          <select
            value={form.interval}
            onChange={(e) => setForm((f) => ({ ...f, interval: e.target.value }))}
            className="w-full rounded-lg border border-white/10 bg-slate-800 px-3 py-1.5 text-xs text-white focus:border-emerald-500/50 focus:outline-none"
          >
            {INTERVALS.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-500">Lookback Days</label>
          <input
            type="number"
            min={7}
            max={365}
            value={form.lookback_days}
            onChange={(e) => { const v = parseInt(e.target.value, 10); setForm((f) => ({ ...f, lookback_days: Number.isFinite(v) ? v : 30 })); }}
            className="w-full rounded-lg border border-white/10 bg-slate-800 px-3 py-1.5 text-xs text-white focus:border-emerald-500/50 focus:outline-none"
          />
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-400">
          {error}
        </div>
      )}

      <button
        onClick={handleRun}
        disabled={running}
        className="mb-6 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
      >
        {running ? "Running..." : "Run Backtest"}
      </button>

      {/* Results table */}
      {results.length === 0 ? (
        <p className="text-sm text-slate-500">No backtest results yet. Run your first backtest above.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/5 text-slate-500">
                <th className="py-2 text-left">Strategy</th>
                <th className="py-2 text-left">Symbol</th>
                <th className="py-2 text-right">Return</th>
                <th className="py-2 text-right">Sharpe</th>
                <th className="py-2 text-right">Max DD</th>
                <th className="py-2 text-right">Win Rate</th>
                <th className="py-2 text-right">Trades</th>
              </tr>
            </thead>
            <tbody>
              {results.slice(0, 10).map((r: any, i: number) => (
                <tr key={i} className="border-b border-white/5">
                  <td className="py-2 text-slate-300">{r.strategy_id}</td>
                  <td className="py-2 text-slate-300">{r.symbol}</td>
                  <td
                    className={`py-2 text-right ${
                      (r.total_return ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    {fmt(r.total_return)}%
                  </td>
                  <td className="py-2 text-right text-white">{fmt(r.sharpe_ratio)}</td>
                  <td className="py-2 text-right text-red-400">{fmt(r.max_drawdown)}%</td>
                  <td className="py-2 text-right text-white">{pct(r.win_rate)}</td>
                  <td className="py-2 text-right text-slate-400">{r.total_trades ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function QuantPage() {
  const [selectedSymbol, setSelectedSymbol] = useState("BTCUSDT");

  const { data: status } = useSWR("/api/quant/status", fetcher, {
    refreshInterval: 15000,
  });

  const { data: analysis, isLoading: analysisLoading } = useSWR(
    `/api/quant/analysis/${selectedSymbol}`,
    fetcher,
    { refreshInterval: 60000 }
  );

  const { data: perfData } = useSWR("/api/quant/performance", fetcher, {
    refreshInterval: 300000,
  });

  const { data: backtestData, mutate: mutateBacktests } = useSWR(
    "/api/quant/backtest",
    fetcher,
    { refreshInterval: 0 }
  );

  return (
    <AppShell
      title="Quant Engine"
      description="Motor cuantitativo determinista: indicadores, régimen, entropy filter y backtesting"
    >
      <div className="space-y-8">
        {/* Engine Status */}
        <EngineStatusCard status={status} />

        {/* Market Analysis */}
        <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
            <h2 className="text-lg font-semibold text-white">Market Analysis</h2>
            {/* Symbol tabs */}
            <div className="flex flex-wrap gap-1">
              {SYMBOLS.map((sym) => (
                <button
                  key={sym}
                  onClick={() => setSelectedSymbol(sym)}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition-all ${
                    selectedSymbol === sym
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                      : "text-slate-500 hover:text-white border border-transparent hover:bg-white/5"
                  }`}
                >
                  {sym.replace("USDT", "")}
                </button>
              ))}
            </div>
          </div>
          <AnalysisCard
            symbol={selectedSymbol}
            analysis={analysis}
            loading={analysisLoading}
          />
        </div>

        {/* Performance Metrics */}
        <PerformanceCard perfData={perfData} />

        {/* Backtesting */}
        <BacktestCard
          backtestData={backtestData}
          onRun={() => mutateBacktests()}
        />
      </div>
    </AppShell>
  );
}
