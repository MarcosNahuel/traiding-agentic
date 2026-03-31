/**
 * GET /api/portfolio/pnl-chart - PnL acumulado para gráfico + resumen por período
 */

import { NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET() {
  try {
    const supabase = createServerClient();

    const { data, error } = await supabase
      .from("positions")
      .select("closed_at, realized_pnl")
      .eq("status", "closed")
      .not("closed_at", "is", null)
      .order("closed_at", { ascending: true });

    if (error) {
      return NextResponse.json(
        { error: "Failed to fetch positions", details: error.message },
        { status: 500 }
      );
    }

    const positions = data ?? [];

    // ── Construir serie diaria acumulada ────────────────────────────────────
    const dailyMap = new Map<string, number>();

    for (const pos of positions) {
      if (!pos.closed_at) continue;
      const day = pos.closed_at.slice(0, 10); // "2025-03-15"
      const pnl = parseFloat(pos.realized_pnl || "0");
      dailyMap.set(day, (dailyMap.get(day) ?? 0) + pnl);
    }

    const sortedDays = Array.from(dailyMap.keys()).sort();
    let cumulative = 0;
    const chartData = sortedDays.map((date) => {
      const daily = dailyMap.get(date)!;
      cumulative += daily;
      return {
        date,
        daily: parseFloat(daily.toFixed(2)),
        cumulative: parseFloat(cumulative.toFixed(2)),
      };
    });

    // ── Calcular rendimiento por período ────────────────────────────────────
    const now = new Date();

    function startOf(daysAgo: number): Date {
      const d = new Date(now);
      d.setHours(0, 0, 0, 0);
      if (daysAgo > 0) d.setDate(d.getDate() - daysAgo);
      return d;
    }

    function calcPeriod(since: Date) {
      const filtered = positions.filter(
        (p) => p.closed_at && new Date(p.closed_at) >= since
      );
      const pnl = filtered.reduce(
        (s, p) => s + parseFloat(p.realized_pnl || "0"),
        0
      );
      const wins = filtered.filter((p) => parseFloat(p.realized_pnl || "0") > 0)
        .length;
      return {
        pnl: parseFloat(pnl.toFixed(2)),
        trades: filtered.length,
        wins,
      };
    }

    return NextResponse.json({
      chartData,
      periods: {
        today: calcPeriod(startOf(0)),
        week: calcPeriod(startOf(6)),
        month: calcPeriod(startOf(29)),
      },
    });
  } catch (err) {
    console.error("Error in GET /api/portfolio/pnl-chart:", err);
    return NextResponse.json(
      {
        error: "Internal server error",
        details: err instanceof Error ? err.message : String(err),
      },
      { status: 500 }
    );
  }
}
