/**
 * GET /api/trades/recent - últimos trades cerrados (para la lista del dashboard).
 */

import { NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET() {
  try {
    const supabase = createServerClient();

    const { data, error } = await supabase
      .from("positions")
      .select(
        "symbol, side, entry_price, exit_price, realized_pnl, realized_pnl_percent, opened_at, closed_at"
      )
      .eq("status", "closed")
      .not("closed_at", "is", null)
      .order("closed_at", { ascending: false })
      .limit(12);

    if (error) {
      return NextResponse.json(
        { error: "Failed to fetch trades", details: error.message },
        { status: 500 }
      );
    }

    const trades = (data ?? []).map((t) => ({
      symbol: t.symbol,
      side: t.side,
      entry: parseFloat(t.entry_price ?? "0"),
      exit: parseFloat(t.exit_price ?? "0"),
      pnl: parseFloat(t.realized_pnl ?? "0"),
      pnlPct: parseFloat(t.realized_pnl_percent ?? "0"),
      closedAt: t.closed_at,
    }));

    return NextResponse.json({ trades });
  } catch (err) {
    return NextResponse.json(
      { error: "Internal server error", details: err instanceof Error ? err.message : String(err) },
      { status: 500 }
    );
  }
}
