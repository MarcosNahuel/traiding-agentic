/**
 * GET /api/binance/test
 * Test Binance Testnet connection
 */

import { NextResponse } from "next/server";
import {
  ping,
  getServerTime,
  getPrice,
  getAccountInfo,
  getBalance,
  BINANCE_CONFIG,
} from "@/lib/exchanges/binance-testnet";

export async function GET() {
  try {
    const results: any = {
      timestamp: new Date().toISOString(),
      config: {
        env: BINANCE_CONFIG.ENV,
        restBase: BINANCE_CONFIG.REST_BASE,
        wsBase: BINANCE_CONFIG.WS_BASE,
        apiKeyConfigured: !!BINANCE_CONFIG.API_KEY,
        secretConfigured: !!BINANCE_CONFIG.API_SECRET,
      },
      tests: {},
    };

    // Test 1: Ping
    try {
      const pingResult = await ping();
      results.tests.ping = {
        status: pingResult ? "success" : "failed",
        message: pingResult ? "Connection OK" : "Connection failed",
      };
    } catch (error) {
      results.tests.ping = {
        status: "error",
        error: error instanceof Error ? error.message : String(error),
      };
    }

    // Test 2: Server time
    try {
      const serverTime = await getServerTime();
      results.tests.serverTime = {
        status: "success",
        serverTime: new Date(serverTime.serverTime).toISOString(),
      };
    } catch (error) {
      results.tests.serverTime = {
        status: "error",
        error: error instanceof Error ? error.message : String(error),
      };
    }

    // Test 3: Get BTC price (public API)
    try {
      const price = await getPrice("BTCUSDT");
      results.tests.getPrice = {
        status: "success",
        btcPrice: `$${parseFloat(price.price).toLocaleString()}`,
      };
    } catch (error) {
      results.tests.getPrice = {
        status: "error",
        error: error instanceof Error ? error.message : String(error),
      };
    }

    // Test 4: Get account info (signed API)
    try {
      const account = await getAccountInfo();
      results.tests.accountInfo = {
        status: "success",
        canTrade: account.canTrade,
        canWithdraw: account.canWithdraw,
        canDeposit: account.canDeposit,
        updateTime: new Date(account.updateTime).toISOString(),
      };
    } catch (error) {
      results.tests.accountInfo = {
        status: "error",
        error: error instanceof Error ? error.message : String(error),
      };
    }

    // Test 5: Get balances
    try {
      const usdtBalance = await getBalance("USDT");
      const btcBalance = await getBalance("BTC");

      results.tests.balances = {
        status: "success",
        USDT: {
          free: parseFloat(usdtBalance.free),
          locked: parseFloat(usdtBalance.locked),
          total: parseFloat(usdtBalance.free) + parseFloat(usdtBalance.locked),
        },
        BTC: {
          free: parseFloat(btcBalance.free),
          locked: parseFloat(btcBalance.locked),
          total: parseFloat(btcBalance.free) + parseFloat(btcBalance.locked),
        },
      };
    } catch (error) {
      results.tests.balances = {
        status: "error",
        error: error instanceof Error ? error.message : String(error),
      };
    }

    // Overall status
    const allTestsPassed = Object.values(results.tests).every(
      (test: any) => test.status === "success"
    );

    return NextResponse.json({
      success: allTestsPassed,
      message: allTestsPassed
        ? "All tests passed! Binance Testnet is ready."
        : "Some tests failed. Check details below.",
      ...results,
    });
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        error: "Test suite failed",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
