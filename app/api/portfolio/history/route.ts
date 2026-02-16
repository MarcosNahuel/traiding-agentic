/**
 * GET /api/portfolio/history - Get trade history
 *
 * Returns closed positions with P&L details
 */

import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);

    // Query parameters
    const symbol = searchParams.get("symbol");
    const status = searchParams.get("status") || "closed";
    const limit = parseInt(searchParams.get("limit") || "50");
    const offset = parseInt(searchParams.get("offset") || "0");
    const startDate = searchParams.get("start_date");
    const endDate = searchParams.get("end_date");

    const supabase = createServerClient();

    // Build query
    let query = supabase
      .from("positions")
      .select("*, strategies_found(name, description)", { count: "exact" })
      .order("closed_at", { ascending: false })
      .range(offset, offset + limit - 1);

    // Apply filters
    if (status) {
      query = query.eq("status", status);
    }

    if (symbol) {
      query = query.eq("symbol", symbol);
    }

    if (startDate) {
      query = query.gte("closed_at", startDate);
    }

    if (endDate) {
      query = query.lte("closed_at", endDate);
    }

    const { data, error, count } = await query;

    if (error) {
      return NextResponse.json(
        { error: "Failed to fetch history", details: error.message },
        { status: 500 }
      );
    }

    // ========================================================================
    // CALCULATE SUMMARY STATS
    // ========================================================================

    const totalPnL = data?.reduce(
      (sum, pos) => sum + parseFloat(pos.realized_pnl || "0"),
      0
    ) || 0;

    const winningTrades =
      data?.filter((pos) => parseFloat(pos.realized_pnl || "0") > 0)
        .length || 0;
    const losingTrades = (data?.length || 0) - winningTrades;

    const avgPnL = data?.length ? totalPnL / data.length : 0;

    const bestTrade = data?.reduce((best, pos) => {
      const pnl = parseFloat(pos.realized_pnl || "0");
      return !best || pnl > parseFloat(best.realized_pnl || "0")
        ? pos
        : best;
    }, null as any);

    const worstTrade = data?.reduce((worst, pos) => {
      const pnl = parseFloat(pos.realized_pnl || "0");
      return !worst || pnl < parseFloat(worst.realized_pnl || "0")
        ? pos
        : worst;
    }, null as any);

    // ========================================================================
    // RETURN HISTORY
    // ========================================================================

    return NextResponse.json({
      positions: data || [],
      total: count || 0,
      limit,
      offset,
      summary: {
        totalPnL: totalPnL.toFixed(2),
        avgPnL: avgPnL.toFixed(2),
        winningTrades,
        losingTrades,
        winRate:
          data?.length && data.length > 0
            ? ((winningTrades / data.length) * 100).toFixed(2)
            : "0.00",
        bestTrade: bestTrade
          ? {
              symbol: bestTrade.symbol,
              pnl: parseFloat(bestTrade.realized_pnl).toFixed(2),
              pnlPercent: parseFloat(
                bestTrade.realized_pnl_percent
              ).toFixed(2),
              date: bestTrade.closed_at,
            }
          : null,
        worstTrade: worstTrade
          ? {
              symbol: worstTrade.symbol,
              pnl: parseFloat(worstTrade.realized_pnl).toFixed(2),
              pnlPercent: parseFloat(
                worstTrade.realized_pnl_percent
              ).toFixed(2),
              date: worstTrade.closed_at,
            }
          : null,
      },
    });
  } catch (error) {
    console.error("Error in GET /api/portfolio/history:", error);
    return NextResponse.json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
