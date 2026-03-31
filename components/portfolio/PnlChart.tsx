"use client";

import { useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

export interface ChartPoint {
  date: string; // "YYYY-MM-DD"
  daily: number;
  cumulative: number;
}

interface PnlChartProps {
  data: ChartPoint[];
  /** ISO date string "YYYY-MM-DD" — filter from this date onwards. Null = show all. */
  cutoffIso: string | null;
}

function formatDate(dateStr: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-AR", {
    month: "short",
    day: "numeric",
  });
}

function formatUSD(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}$${Math.abs(value).toFixed(2)}`;
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const cum: number = payload[0]?.value ?? 0;
  const daily: number = payload[1]?.value ?? 0;
  return (
    <div className="rounded-lg border border-white/10 bg-slate-800 p-3 text-xs shadow-xl">
      <p className="mb-1.5 text-slate-400">{formatDate(label)}</p>
      <p className={`font-mono font-semibold ${cum >= 0 ? "text-emerald-400" : "text-red-400"}`}>
        Acumulado: {formatUSD(cum)}
      </p>
      <p className={`mt-0.5 font-mono ${daily >= 0 ? "text-emerald-300" : "text-red-300"}`}>
        Este día: {formatUSD(daily)}
      </p>
    </div>
  );
}

export default function PnlChart({ data, cutoffIso }: PnlChartProps) {
  const { adjusted, color } = useMemo(() => {
    // ISO date string comparison works because "YYYY-MM-DD" is lexicographically ordered
    const filtered =
      cutoffIso === null
        ? data
        : data.filter((p) => p.date >= cutoffIso);

    // Re-base cumulative to start at 0 for the selected period
    const base =
      filtered.length > 0 && cutoffIso !== null
        ? (filtered[0]?.cumulative ?? 0) - (filtered[0]?.daily ?? 0)
        : 0;

    const adj = filtered.map((p) => ({
      ...p,
      cumulative: parseFloat((p.cumulative - base).toFixed(2)),
    }));

    const lastCum = adj[adj.length - 1]?.cumulative ?? 0;
    return {
      adjusted: adj,
      color: lastCum >= 0 ? "#10b981" : "#ef4444",
    };
  }, [data, cutoffIso]);

  if (adjusted.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-slate-500">
        Sin datos para este período. Los trades aparecerán aquí al cerrarse.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={adjusted} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.3} />
            <stop offset="95%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="rgba(255,255,255,0.04)"
          vertical={false}
        />
        <XAxis
          dataKey="date"
          tickFormatter={formatDate}
          tick={{ fill: "#64748b", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tickFormatter={(v) => `$${v}`}
          tick={{ fill: "#64748b", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          width={55}
        />
        <ReferenceLine y={0} stroke="rgba(255,255,255,0.12)" strokeDasharray="4 4" />
        <Tooltip content={<CustomTooltip />} />
        <Area
          type="monotone"
          dataKey="cumulative"
          stroke={color}
          strokeWidth={2}
          fill="url(#pnlGrad)"
          dot={false}
          activeDot={{ r: 4, fill: color, stroke: "transparent" }}
        />
        {/* Serie oculta solo para exponer `daily` en el tooltip */}
        <Area
          type="monotone"
          dataKey="daily"
          stroke="transparent"
          fill="transparent"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
