/**
 * GET /api/portfolio - Get current portfolio state
 *
 * Returns:
 * - Account balance
 * - Open positions
 * - P&L summary
 * - Performance metrics
 */

import { NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";
import { getBalance, getPrice } from "@/lib/exchanges/binance-testnet";

export async function GET() {
  try {
    const supabase = createServerClient();

    // ========================================================================
    // FETCH ACCOUNT BALANCE
    // ========================================================================

    let usdtBalance = { free: "0", locked: "0" };
    let btcBalance = { free: "0", locked: "0" };
    let exchangeError: string | null = null;

    try {
      usdtBalance = await getBalance("USDT");
      btcBalance = await getBalance("BTC");
    } catch (error) {
      exchangeError =
        error instanceof Error ? error.message : String(error);
      console.warn(
        "Binance balance fetch failed, falling back to snapshot/zero balances:",
        exchangeError
      );
    }

    const totalBalance =
      parseFloat(usdtBalance.free) + parseFloat(usdtBalance.locked);
    const availableBalance = parseFloat(usdtBalance.free);
    const lockedBalance = parseFloat(usdtBalance.locked);

    // ========================================================================
    // FETCH OPEN POSITIONS
    // ========================================================================

    const { data: openPositions } = await supabase
      .from("positions")
      .select("*")
      .eq("status", "open")
      .order("opened_at", { ascending: false });

    // Update unrealized P&L for open positions
    const positionsWithPnL = await Promise.all(
      (openPositions || []).map(async (pos) => {
        try {
          const priceData = await getPrice(pos.symbol);
          const currentPrice = parseFloat(priceData.price);

          const priceDiff = currentPrice - parseFloat(pos.entry_price);
          const unrealizedPnL =
            priceDiff * parseFloat(pos.current_quantity) -
            parseFloat(pos.total_commission);
          const unrealizedPnLPercent =
            (unrealizedPnL / parseFloat(pos.entry_notional)) * 100;

          // Update position in DB
          await supabase
            .from("positions")
            .update({
              current_price: currentPrice,
              unrealized_pnl: unrealizedPnL,
              unrealized_pnl_percent: unrealizedPnLPercent,
              updated_at: new Date().toISOString(),
            })
            .eq("id", pos.id);

          return {
            ...pos,
            current_price: currentPrice,
            unrealized_pnl: unrealizedPnL,
            unrealized_pnl_percent: unrealizedPnLPercent,
          };
        } catch (error) {
          console.error(
            `Failed to update price for ${pos.symbol}:`,
            error
          );
          return pos;
        }
      })
    );

    const totalUnrealizedPnL = positionsWithPnL.reduce(
      (sum, pos) => sum + parseFloat(pos.unrealized_pnl || "0"),
      0
    );

    const totalPositionValue = positionsWithPnL.reduce(
      (sum, pos) =>
        sum +
        parseFloat(pos.current_price || pos.entry_price) *
          parseFloat(pos.current_quantity),
      0
    );

    // ========================================================================
    // FETCH CLOSED POSITIONS (Today)
    // ========================================================================

    const today = new Date().toISOString().split("T")[0];

    const { data: closedToday } = await supabase
      .from("positions")
      .select("*")
      .eq("status", "closed")
      .gte("closed_at", today)
      .order("closed_at", { ascending: false });

    const dailyRealizedPnL = (closedToday || []).reduce(
      (sum, pos) => sum + parseFloat(pos.realized_pnl || "0"),
      0
    );

    // ========================================================================
    // FETCH ALL-TIME STATS
    // ========================================================================

    const { data: allClosedPositions } = await supabase
      .from("positions")
      .select("realized_pnl, realized_pnl_percent, closed_at")
      .eq("status", "closed");

    const totalTrades = allClosedPositions?.length || 0;
    const winningTrades =
      allClosedPositions?.filter((pos) => parseFloat(pos.realized_pnl) > 0)
        .length || 0;
    const losingTrades = totalTrades - winningTrades;
    const winRate = totalTrades > 0 ? (winningTrades / totalTrades) * 100 : 0;

    const totalRealizedPnL = allClosedPositions?.reduce(
      (sum, pos) => sum + parseFloat(pos.realized_pnl || "0"),
      0
    ) || 0;

    // ========================================================================
    // CALCULATE DRAWDOWN
    // ========================================================================

    // Get peak balance from snapshots
    const { data: latestSnapshot } = await supabase
      .from("account_snapshots")
      .select(
        "total_balance, peak_balance, max_drawdown, max_drawdown_percent"
      )
      .order("snapshot_date", { ascending: false })
      .limit(1)
      .single();

    const snapshotTotalBalance = latestSnapshot
      ? parseFloat(
          (latestSnapshot as { total_balance?: string | number })
            .total_balance as string
        ) || 0
      : 0;

    const effectiveTotalBalance =
      totalBalance > 0 ? totalBalance : snapshotTotalBalance;
    const effectiveAvailableBalance =
      availableBalance > 0 ? availableBalance : snapshotTotalBalance;

    const peakBalance = latestSnapshot
      ? parseFloat(latestSnapshot.peak_balance)
      : effectiveTotalBalance;
    const currentDrawdown = Math.max(0, peakBalance - effectiveTotalBalance);
    const currentDrawdownPercent =
      peakBalance > 0 ? (currentDrawdown / peakBalance) * 100 : 0;

    // ========================================================================
    // FETCH RISK EVENTS
    // ========================================================================

    const { data: recentRiskEvents } = await supabase
      .from("risk_events")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(10);

    const unresolvedEvents =
      recentRiskEvents?.filter((evt) => !evt.resolved).length || 0;

    // ========================================================================
    // RETURN PORTFOLIO STATE
    // ========================================================================

    return NextResponse.json({
      timestamp: new Date().toISOString(),

      // Account balance
      balance: {
        total: effectiveTotalBalance,
        available: effectiveAvailableBalance,
        locked: lockedBalance,
        inPositions: totalPositionValue,
      },

      // Asset balances
      assets: {
        USDT: {
          free: parseFloat(usdtBalance.free),
          locked: parseFloat(usdtBalance.locked),
          total:
            parseFloat(usdtBalance.free) + parseFloat(usdtBalance.locked),
        },
        BTC: {
          free: parseFloat(btcBalance.free),
          locked: parseFloat(btcBalance.locked),
          total: parseFloat(btcBalance.free) + parseFloat(btcBalance.locked),
        },
      },

      // Positions
      positions: {
        open: positionsWithPnL,
        openCount: positionsWithPnL.length,
        totalValue: totalPositionValue,
        totalUnrealizedPnL,
      },

      // P&L
      pnl: {
        daily: {
          realized: dailyRealizedPnL,
          unrealized: totalUnrealizedPnL,
          total: dailyRealizedPnL + totalUnrealizedPnL,
        },
        allTime: {
          realized: totalRealizedPnL,
          unrealized: totalUnrealizedPnL,
          total: totalRealizedPnL + totalUnrealizedPnL,
        },
      },

      // Performance
      performance: {
        totalTrades,
        winningTrades,
        losingTrades,
        winRate: winRate.toFixed(2),
        avgWin:
          winningTrades > 0
            ? (
                (allClosedPositions
                  ?.filter((pos) => parseFloat(pos.realized_pnl) > 0)
                  .reduce(
                    (sum, pos) => sum + parseFloat(pos.realized_pnl),
                    0
                  ) || 0) / winningTrades
              ).toFixed(2)
            : "0.00",
        avgLoss:
          losingTrades > 0
            ? (
                (allClosedPositions
                  ?.filter((pos) => parseFloat(pos.realized_pnl) < 0)
                  .reduce(
                    (sum, pos) => sum + parseFloat(pos.realized_pnl),
                    0
                  ) || 0) / losingTrades
              ).toFixed(2)
            : "0.00",
      },

      // Risk metrics
      risk: {
        currentDrawdown,
        currentDrawdownPercent: currentDrawdownPercent.toFixed(2),
        maxDrawdown: latestSnapshot
          ? parseFloat(latestSnapshot.max_drawdown)
          : 0,
        maxDrawdownPercent: latestSnapshot
          ? parseFloat(latestSnapshot.max_drawdown_percent)
          : 0,
        peakBalance,
        unresolvedRiskEvents: unresolvedEvents,
      },

      // Recent activity
      recentActivity: {
        closedToday: closedToday?.length || 0,
        riskEvents: recentRiskEvents?.slice(0, 5) || [],
      },

      // Exchange diagnostics
      exchange: {
        connected: exchangeError === null,
        warning: exchangeError,
      },
    });
  } catch (error) {
    console.error("Error in GET /api/portfolio:", error);
    return NextResponse.json(
      {
        error: "Failed to fetch portfolio",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
