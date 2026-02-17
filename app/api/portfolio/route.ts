import { NextRequest, NextResponse } from "next/server";
import { isPythonBackendEnabled, getPortfolio } from "@/lib/trading/python-backend";
import { createServerClient } from "@/lib/supabase";
import { getBalance, getPrice } from "@/lib/exchanges/binance-client";

function transformPythonPortfolio(p: Record<string, any>) {
  const positions: any[] = Array.isArray(p.positions) ? p.positions : [];
  const totalValue = typeof p.in_positions === "number" ? p.in_positions : 0;
  const totalTrades: number = p.total_trades ?? 0;
  const winRate: number = p.win_rate ?? 0;
  const winningTrades = Math.round(totalTrades * winRate / 100);
  const losingTrades = totalTrades - winningTrades;

  return {
    timestamp: new Date().toISOString(),
    balance: {
      total: p.total_portfolio_value ?? 0,
      available: p.usdt_balance ?? 0,
      locked: 0,
      inPositions: totalValue,
    },
    positions: {
      open: positions,
      openCount: positions.length,
      totalValue,
      totalUnrealizedPnL: p.unrealized_pnl ?? 0,
    },
    pnl: {
      daily: {
        realized: (p.daily_pnl ?? 0) - (p.unrealized_pnl ?? 0),
        unrealized: p.unrealized_pnl ?? 0,
        total: p.daily_pnl ?? 0,
      },
      allTime: {
        realized: p.all_time_pnl ?? 0,
        unrealized: p.unrealized_pnl ?? 0,
        total: (p.all_time_pnl ?? 0) + (p.unrealized_pnl ?? 0),
      },
    },
    performance: {
      totalTrades,
      winningTrades,
      losingTrades,
      winRate: winRate.toFixed(2),
      avgWin: "0.00",
      avgLoss: "0.00",
    },
    risk: {
      currentDrawdown: 0,
      currentDrawdownPercent: "0.00",
      maxDrawdown: 0,
      maxDrawdownPercent: 0,
      peakBalance: p.total_portfolio_value ?? 0,
      unresolvedRiskEvents: 0,
    },
    recentActivity: { closedToday: 0, riskEvents: [] },
    exchange: { connected: true, warning: null },
  };
}

export async function GET(_request: NextRequest) {
  try {
    if (isPythonBackendEnabled()) {
      const raw = await getPortfolio() as Record<string, any>;
      // Python backend returns a flat shape; transform to the shape the frontend expects
      return NextResponse.json(transformPythonPortfolio(raw));
    }

    // Fallback: inline original Next.js portfolio logic
    const supabase = createServerClient();

    let usdtBalance = { free: "0", locked: "0" };
    let btcBalance = { free: "0", locked: "0" };
    let exchangeError: string | null = null;

    try {
      usdtBalance = await getBalance("USDT");
      btcBalance = await getBalance("BTC");
    } catch (error) {
      exchangeError = error instanceof Error ? error.message : String(error);
      console.warn("Binance balance fetch failed:", exchangeError);
    }

    const totalBalance = parseFloat(usdtBalance.free) + parseFloat(usdtBalance.locked);
    const availableBalance = parseFloat(usdtBalance.free);
    const lockedBalance = parseFloat(usdtBalance.locked);

    const { data: openPositions } = await supabase
      .from("positions")
      .select("*")
      .eq("status", "open")
      .order("opened_at", { ascending: false });

    const positionsWithPnL = await Promise.all(
      (openPositions || []).map(async (pos) => {
        try {
          const priceData = await getPrice(pos.symbol);
          const currentPrice = parseFloat(priceData.price);
          const priceDiff = currentPrice - parseFloat(pos.entry_price);
          const unrealizedPnL = priceDiff * parseFloat(pos.current_quantity) - parseFloat(pos.total_commission);
          const unrealizedPnLPercent = (unrealizedPnL / parseFloat(pos.entry_notional)) * 100;
          await supabase.from("positions").update({
            current_price: currentPrice,
            unrealized_pnl: unrealizedPnL,
            unrealized_pnl_percent: unrealizedPnLPercent,
            updated_at: new Date().toISOString(),
          }).eq("id", pos.id);
          return { ...pos, current_price: currentPrice, unrealized_pnl: unrealizedPnL, unrealized_pnl_percent: unrealizedPnLPercent };
        } catch {
          return pos;
        }
      })
    );

    const totalUnrealizedPnL = positionsWithPnL.reduce((sum, pos) => sum + parseFloat(pos.unrealized_pnl || "0"), 0);
    const totalPositionValue = positionsWithPnL.reduce(
      (sum, pos) => sum + parseFloat(pos.current_price || pos.entry_price) * parseFloat(pos.current_quantity),
      0
    );

    const today = new Date().toISOString().split("T")[0];
    const { data: closedToday } = await supabase.from("positions").select("*").eq("status", "closed").gte("closed_at", today).order("closed_at", { ascending: false });
    const dailyRealizedPnL = (closedToday || []).reduce((sum, pos) => sum + parseFloat(pos.realized_pnl || "0"), 0);

    const { data: allClosedPositions } = await supabase.from("positions").select("realized_pnl, realized_pnl_percent, closed_at").eq("status", "closed");
    const totalTrades = allClosedPositions?.length || 0;
    const winningTrades = allClosedPositions?.filter((pos) => parseFloat(pos.realized_pnl) > 0).length || 0;
    const losingTrades = totalTrades - winningTrades;
    const winRate = totalTrades > 0 ? (winningTrades / totalTrades) * 100 : 0;
    const totalRealizedPnL = allClosedPositions?.reduce((sum, pos) => sum + parseFloat(pos.realized_pnl || "0"), 0) || 0;

    const { data: latestSnapshot } = await supabase.from("account_snapshots").select("total_balance, peak_balance, max_drawdown, max_drawdown_percent").order("snapshot_date", { ascending: false }).limit(1).single();

    const snapshotTotalBalance = latestSnapshot ? parseFloat((latestSnapshot as { total_balance?: string | number }).total_balance as string) || 0 : 0;
    const effectiveTotalBalance = totalBalance > 0 ? totalBalance : snapshotTotalBalance;
    const effectiveAvailableBalance = availableBalance > 0 ? availableBalance : snapshotTotalBalance;
    const peakBalance = latestSnapshot ? parseFloat(latestSnapshot.peak_balance) : effectiveTotalBalance;
    const currentDrawdown = Math.max(0, peakBalance - effectiveTotalBalance);
    const currentDrawdownPercent = peakBalance > 0 ? (currentDrawdown / peakBalance) * 100 : 0;

    const { data: recentRiskEvents } = await supabase.from("risk_events").select("*").order("created_at", { ascending: false }).limit(10);
    const unresolvedEvents = recentRiskEvents?.filter((evt) => !evt.resolved).length || 0;

    return NextResponse.json({
      timestamp: new Date().toISOString(),
      balance: { total: effectiveTotalBalance, available: effectiveAvailableBalance, locked: lockedBalance, inPositions: totalPositionValue },
      assets: {
        USDT: { free: parseFloat(usdtBalance.free), locked: parseFloat(usdtBalance.locked), total: parseFloat(usdtBalance.free) + parseFloat(usdtBalance.locked) },
        BTC: { free: parseFloat(btcBalance.free), locked: parseFloat(btcBalance.locked), total: parseFloat(btcBalance.free) + parseFloat(btcBalance.locked) },
      },
      positions: { open: positionsWithPnL, openCount: positionsWithPnL.length, totalValue: totalPositionValue, totalUnrealizedPnL },
      pnl: {
        daily: { realized: dailyRealizedPnL, unrealized: totalUnrealizedPnL, total: dailyRealizedPnL + totalUnrealizedPnL },
        allTime: { realized: totalRealizedPnL, unrealized: totalUnrealizedPnL, total: totalRealizedPnL + totalUnrealizedPnL },
      },
      performance: {
        totalTrades, winningTrades, losingTrades,
        winRate: winRate.toFixed(2),
        avgWin: winningTrades > 0 ? ((allClosedPositions?.filter((p) => parseFloat(p.realized_pnl) > 0).reduce((s, p) => s + parseFloat(p.realized_pnl), 0) || 0) / winningTrades).toFixed(2) : "0.00",
        avgLoss: losingTrades > 0 ? ((allClosedPositions?.filter((p) => parseFloat(p.realized_pnl) < 0).reduce((s, p) => s + parseFloat(p.realized_pnl), 0) || 0) / losingTrades).toFixed(2) : "0.00",
      },
      risk: {
        currentDrawdown,
        currentDrawdownPercent: currentDrawdownPercent.toFixed(2),
        maxDrawdown: latestSnapshot ? parseFloat(latestSnapshot.max_drawdown) : 0,
        maxDrawdownPercent: latestSnapshot ? parseFloat(latestSnapshot.max_drawdown_percent) : 0,
        peakBalance,
        unresolvedRiskEvents: unresolvedEvents,
      },
      recentActivity: { closedToday: closedToday?.length || 0, riskEvents: recentRiskEvents?.slice(0, 5) || [] },
      exchange: { connected: exchangeError === null, warning: exchangeError },
    });
  } catch (e: unknown) {
    console.error("GET /api/portfolio error:", e);
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
