"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import { AppShell } from "@/components/ui/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";

const fetcher = async (url: string) => {
  const response = await fetch(url);
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(
      payload?.details || payload?.error || `HTTP ${response.status}`
    );
  }

  return payload;
};

export default function PortfolioPage() {
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Fetch portfolio data
  const { data: portfolio, error, mutate } = useSWR(
    "/api/portfolio",
    fetcher,
    {
      refreshInterval: 30000, // Refresh every 30 seconds
    }
  );

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await mutate();
    setIsRefreshing(false);
  };

  if (error) {
    return (
      <AppShell>
        <div className="min-h-screen bg-gray-50 p-8">
          <div className="mx-auto max-w-7xl">
            <div className="rounded-lg bg-red-50 p-4 text-red-800">
              <h3 className="font-semibold">Error loading portfolio</h3>
              <p className="text-sm">{error.message}</p>
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  if (!portfolio) {
    return (
      <AppShell>
        <div className="min-h-screen bg-gray-50 p-8">
          <div className="mx-auto max-w-7xl">
            <div className="animate-pulse space-y-4">
              <div className="h-32 rounded-lg bg-gray-200"></div>
              <div className="grid grid-cols-3 gap-4">
                <div className="h-24 rounded-lg bg-gray-200"></div>
                <div className="h-24 rounded-lg bg-gray-200"></div>
                <div className="h-24 rounded-lg bg-gray-200"></div>
              </div>
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  const balance = portfolio?.balance ?? {
    total: 0,
    available: 0,
    inPositions: 0,
    locked: 0,
  };
  const positions = portfolio?.positions ?? {
    open: [],
    openCount: 0,
    totalValue: 0,
  };
  const pnl = portfolio?.pnl ?? {
    daily: { realized: 0, unrealized: 0, total: 0 },
    allTime: { realized: 0, unrealized: 0, total: 0 },
  };
  const performance = portfolio?.performance ?? {
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

  return (
    <AppShell>
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="mx-auto max-w-7xl space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Portfolio</h1>
              <p className="text-sm text-gray-500">
                Real-time trading performance
              </p>
            </div>
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {isRefreshing ? "Refreshing..." : "Refresh"}
            </button>
          </div>

          {/* Balance Overview */}
          <div className="grid grid-cols-1 gap-6 md:grid-cols-4">
            <div className="rounded-lg bg-white p-6 shadow">
              <p className="text-sm text-gray-500">Total Balance</p>
              <p className="mt-2 text-3xl font-bold text-gray-900">
                ${balance.total.toLocaleString()}
              </p>
            </div>
            <div className="rounded-lg bg-white p-6 shadow">
              <p className="text-sm text-gray-500">Available</p>
              <p className="mt-2 text-3xl font-bold text-green-600">
                ${balance.available.toLocaleString()}
              </p>
            </div>
            <div className="rounded-lg bg-white p-6 shadow">
              <p className="text-sm text-gray-500">In Positions</p>
              <p className="mt-2 text-3xl font-bold text-blue-600">
                ${balance.inPositions.toLocaleString()}
              </p>
            </div>
            <div className="rounded-lg bg-white p-6 shadow">
              <p className="text-sm text-gray-500">Locked</p>
              <p className="mt-2 text-3xl font-bold text-gray-600">
                ${balance.locked.toLocaleString()}
              </p>
            </div>
          </div>

          {/* P&L Cards */}
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {/* Daily P&L */}
            <div className="rounded-lg bg-white p-6 shadow">
              <h3 className="text-lg font-semibold text-gray-900">
                Daily P&L
              </h3>
              <div className="mt-4 space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Realized:</span>
                  <span
                    className={`text-sm font-medium ${
                      pnl.daily.realized >= 0
                        ? "text-green-600"
                        : "text-red-600"
                    }`}
                  >
                    {pnl.daily.realized >= 0 ? "+" : ""}$
                    {pnl.daily.realized.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Unrealized:</span>
                  <span
                    className={`text-sm font-medium ${
                      pnl.daily.unrealized >= 0
                        ? "text-green-600"
                        : "text-red-600"
                    }`}
                  >
                    {pnl.daily.unrealized >= 0 ? "+" : ""}$
                    {pnl.daily.unrealized.toFixed(2)}
                  </span>
                </div>
                <div className="border-t pt-2">
                  <div className="flex justify-between">
                    <span className="font-medium text-gray-900">Total:</span>
                    <span
                      className={`text-lg font-bold ${
                        pnl.daily.total >= 0
                          ? "text-green-600"
                          : "text-red-600"
                      }`}
                    >
                      {pnl.daily.total >= 0 ? "+" : ""}$
                      {pnl.daily.total.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* All-Time P&L */}
            <div className="rounded-lg bg-white p-6 shadow">
              <h3 className="text-lg font-semibold text-gray-900">
                All-Time P&L
              </h3>
              <div className="mt-4 space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Realized:</span>
                  <span
                    className={`text-sm font-medium ${
                      pnl.allTime.realized >= 0
                        ? "text-green-600"
                        : "text-red-600"
                    }`}
                  >
                    {pnl.allTime.realized >= 0 ? "+" : ""}$
                    {pnl.allTime.realized.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Unrealized:</span>
                  <span
                    className={`text-sm font-medium ${
                      pnl.allTime.unrealized >= 0
                        ? "text-green-600"
                        : "text-red-600"
                    }`}
                  >
                    {pnl.allTime.unrealized >= 0 ? "+" : ""}$
                    {pnl.allTime.unrealized.toFixed(2)}
                  </span>
                </div>
                <div className="border-t pt-2">
                  <div className="flex justify-between">
                    <span className="font-medium text-gray-900">Total:</span>
                    <span
                      className={`text-lg font-bold ${
                        pnl.allTime.total >= 0
                          ? "text-green-600"
                          : "text-red-600"
                      }`}
                    >
                      {pnl.allTime.total >= 0 ? "+" : ""}$
                      {pnl.allTime.total.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Performance Stats */}
          <div className="rounded-lg bg-white p-6 shadow">
            <h3 className="text-lg font-semibold text-gray-900">
              Performance
            </h3>
            <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-5">
              <div>
                <p className="text-sm text-gray-500">Total Trades</p>
                <p className="mt-1 text-2xl font-bold text-gray-900">
                  {performance.totalTrades}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Winning</p>
                <p className="mt-1 text-2xl font-bold text-green-600">
                  {performance.winningTrades}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Losing</p>
                <p className="mt-1 text-2xl font-bold text-red-600">
                  {performance.losingTrades}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Win Rate</p>
                <p className="mt-1 text-2xl font-bold text-blue-600">
                  {performance.winRate}%
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Avg Win</p>
                <p className="mt-1 text-2xl font-bold text-green-600">
                  ${performance.avgWin}
                </p>
              </div>
            </div>
          </div>

          {/* Open Positions */}
          <div className="rounded-lg bg-white p-6 shadow">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">
                Open Positions ({positions.openCount})
              </h3>
              <span className="text-sm text-gray-500">
                Total: ${positions.totalValue.toFixed(2)}
              </span>
            </div>

            {positions.open.length === 0 ? (
              <div className="mt-4 text-center text-gray-500">
                <p>No open positions</p>
              </div>
            ) : (
              <div className="mt-4 overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead>
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                        Symbol
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                        Side
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                        Entry
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                        Current
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                        Quantity
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                        P&L
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {positions.open.map((pos: any) => (
                      <tr key={pos.id} className="hover:bg-gray-50">
                        <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                          {pos.symbol}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-sm">
                          <StatusBadge
                            status={pos.side}
                            variant={
                              pos.side === "long" ? "success" : "warning"
                            }
                          />
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-900">
                          ${Number(pos.entry_price ?? 0).toLocaleString()}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-900">
                          ${Number(pos.current_price ?? 0).toLocaleString()}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-900">
                          {Number(pos.current_quantity ?? 0)}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-right text-sm">
                          <div
                            className={`font-medium ${
                              Number(pos.unrealized_pnl ?? 0) >= 0
                                ? "text-green-600"
                                : "text-red-600"
                            }`}
                          >
                            {Number(pos.unrealized_pnl ?? 0) >= 0 ? "+" : ""}$
                            {Number(pos.unrealized_pnl ?? 0).toFixed(2)}
                          </div>
                          <div
                            className={`text-xs ${
                              Number(pos.unrealized_pnl_percent ?? 0) >= 0
                                ? "text-green-600"
                                : "text-red-600"
                            }`}
                          >
                            ({Number(pos.unrealized_pnl_percent ?? 0) >= 0 ? "+" : ""}
                            {Number(pos.unrealized_pnl_percent ?? 0).toFixed(2)}%)
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Risk Metrics */}
          <div className="rounded-lg bg-white p-6 shadow">
            <h3 className="text-lg font-semibold text-gray-900">
              Risk Metrics
            </h3>
            <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
              <div>
                <p className="text-sm text-gray-500">Current Drawdown</p>
                <p className="mt-1 text-2xl font-bold text-red-600">
                  ${risk.currentDrawdown.toFixed(2)}
                </p>
                <p className="text-xs text-gray-500">
                  ({risk.currentDrawdownPercent}%)
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Max Drawdown</p>
                <p className="mt-1 text-2xl font-bold text-red-800">
                  ${risk.maxDrawdown.toFixed(2)}
                </p>
                <p className="text-xs text-gray-500">
                  ({risk.maxDrawdownPercent}%)
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Peak Balance</p>
                <p className="mt-1 text-2xl font-bold text-gray-900">
                  ${risk.peakBalance.toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Unresolved Alerts</p>
                <p className="mt-1 text-2xl font-bold text-orange-600">
                  {risk.unresolvedRiskEvents}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
