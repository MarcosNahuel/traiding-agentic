/**
 * Home — Dashboard simple: ¿está resultando el bot?
 * Una sola vista clara: veredicto + curva de P&L + períodos + últimos trades.
 */
"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import useSWR from "swr";
import { Activity, ArrowRight } from "lucide-react";
import type { ChartPoint } from "@/components/portfolio/PnlChart";

const PnlChart = dynamic(() => import("@/components/portfolio/PnlChart"), {
  ssr: false,
  loading: () => <div className="h-64 animate-pulse rounded-xl bg-white/5" />,
});

const fetcher = (url: string) => fetch(url).then((r) => r.json());

const usd = (v: number) => `${v >= 0 ? "+" : "-"}$${Math.abs(v ?? 0).toFixed(2)}`;
const pct = (w: number, t: number) => (t > 0 ? Math.round((w / t) * 100) : 0);

type Period = { pnl: number; trades: number; wins: number };

const NAV: [string, string][] = [
  ["Portfolio", "/portfolio"],
  ["Trades", "/trades"],
  ["Quant", "/quant"],
  ["Strategist", "/daily"],
  ["Logs", "/logs"],
];

export default function HomePage() {
  const { data: chart } = useSWR("/api/portfolio/pnl-chart", fetcher, { refreshInterval: 60_000 });
  const { data: pf } = useSWR("/api/portfolio", fetcher, { refreshInterval: 60_000 });
  const { data: recent } = useSWR("/api/trades/recent", fetcher, { refreshInterval: 60_000 });

  const series: ChartPoint[] = chart?.chartData ?? [];
  const periods: Record<string, Period> = chart?.periods ?? {};
  const month = periods.month ?? { pnl: 0, trades: 0, wins: 0 };
  const week = periods.week ?? { pnl: 0, trades: 0, wins: 0 };

  const balance: number = pf?.balance?.total ?? 0;
  const allTime: number = pf?.pnl?.all_time?.total ?? 0;
  const winRate: number = pf?.winRate ?? 0;
  const totalTrades: number = pf?.totalTrades ?? 0;
  const openCount: number = pf?.positions?.openCount ?? 0;
  const trades = recent?.trades ?? [];

  // ── Veredicto: ¿está resultando o necesita cambios? ──
  let v = { label: "En observación", tone: "warn", note: "Mes mixto." };
  if (month.trades < 5) v = { label: "Pocos datos", tone: "neutral", note: "Muestra chica — esperá más trades para concluir." };
  else if (month.pnl >= 0 && week.pnl >= 0) v = { label: "Funcionando", tone: "good", note: `${usd(month.pnl)} en 30d, semana en verde.` };
  else if (month.pnl < 0) v = { label: "Necesita cambios", tone: "bad", note: `Perdiendo ${usd(month.pnl)} en 30d (régimen/PF desfavorable).` };

  const tones: Record<string, string> = {
    good: "from-emerald-500/20 to-teal-600/10 border-emerald-500/30 text-emerald-300",
    bad: "from-rose-500/20 to-red-600/10 border-rose-500/30 text-rose-300",
    warn: "from-amber-500/20 to-orange-600/10 border-amber-500/30 text-amber-300",
    neutral: "from-slate-500/20 to-slate-600/10 border-white/10 text-slate-300",
  };

  return (
    <div className="min-h-screen bg-transparent text-white">
      <header className="sticky top-0 z-50 border-b border-white/5 bg-slate-950/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-5 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600">
              <Activity className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold tracking-tight">Trading Agentic</span>
            <span className="ml-1 flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] text-emerald-400">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" /> live
            </span>
          </div>
          <nav className="hidden gap-1 text-sm text-slate-400 sm:flex">
            {NAV.map(([label, href]) => (
              <Link key={href} href={href} className="rounded-md px-2.5 py-1 hover:bg-white/5 hover:text-white">
                {label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-5 px-5 py-6">
        {/* Veredicto */}
        <section className={`rounded-2xl border bg-gradient-to-br p-5 ${tones[v.tone]}`}>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-wide opacity-70">¿Está resultando?</p>
              <h2 className="mt-0.5 text-2xl font-extrabold">{v.label}</h2>
              <p className="mt-1 text-sm opacity-90">{v.note}</p>
            </div>
            <div className="flex gap-6 text-right">
              <div>
                <p className="text-[11px] uppercase opacity-60">Balance</p>
                <p className="text-xl font-bold text-white">${balance.toFixed(0)}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase opacity-60">P&L total</p>
                <p className={`text-xl font-bold ${allTime >= 0 ? "text-emerald-400" : "text-rose-400"}`}>{usd(allTime)}</p>
              </div>
            </div>
          </div>
        </section>

        {/* Curva de P&L */}
        <section className="rounded-2xl border border-white/5 bg-white/[0.02] p-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-300">Curva de P&L (acumulado)</h3>
            <Link href="/portfolio" className="flex items-center gap-1 text-xs text-slate-400 hover:text-white">
              detalle <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {series.length > 1 ? (
            <PnlChart data={series} cutoffIso={null} />
          ) : (
            <div className="flex h-48 items-center justify-center text-sm text-slate-500">Sin trades cerrados aún.</div>
          )}
        </section>

        {/* Períodos */}
        <section className="grid grid-cols-3 gap-3">
          {([
            ["Hoy", periods.today],
            ["7 días", week],
            ["30 días", month],
          ] as [string, Period | undefined][]).map(([label, p]) => {
            const per = p ?? { pnl: 0, trades: 0, wins: 0 };
            return (
              <div key={label} className="rounded-xl border border-white/5 bg-white/[0.02] p-3">
                <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
                <p className={`mt-1 text-lg font-bold ${per.pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>{usd(per.pnl)}</p>
                <p className="text-[11px] text-slate-500">{per.trades} trades · {pct(per.wins, per.trades)}% win</p>
              </div>
            );
          })}
        </section>

        {/* Últimos trades */}
        <section className="rounded-2xl border border-white/5 bg-white/[0.02] p-4">
          <div className="mb-3 flex items-center justify-between text-sm">
            <h3 className="font-semibold text-slate-300">Últimos trades</h3>
            <span className="text-xs text-slate-500">
              {totalTrades} totales · {Math.round(winRate)}% win · {openCount} abiertas
            </span>
          </div>
          <div className="divide-y divide-white/5">
            {trades.length === 0 && <p className="py-6 text-center text-sm text-slate-500">Sin trades cerrados.</p>}
            {trades.map((t: any, i: number) => (
              <div key={i} className="flex items-center justify-between py-2 text-sm">
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${t.pnl >= 0 ? "bg-emerald-500" : "bg-rose-500"}`} />
                  <span className="font-medium">{t.symbol}</span>
                  <span className="text-xs text-slate-500">{t.side}</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className={`font-semibold ${t.pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {usd(t.pnl)} <span className="text-xs opacity-70">({t.pnlPct >= 0 ? "+" : ""}{(t.pnlPct ?? 0).toFixed(1)}%)</span>
                  </span>
                  <span className="w-20 text-right text-xs text-slate-500">
                    {t.closedAt ? new Date(t.closedAt).toLocaleDateString("es-AR", { month: "short", day: "numeric" }) : ""}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <p className="pb-4 text-center text-xs text-slate-600">
          El Daily Strategist (Claude) analiza esto cada día y propone ajustes por Telegram.
        </p>
      </main>
    </div>
  );
}
