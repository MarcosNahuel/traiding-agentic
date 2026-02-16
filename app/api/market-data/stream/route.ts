/**
 * POST /api/market-data/stream - Start/stop/manage market data stream
 * GET /api/market-data/stream - Get stream status
 */

import { NextRequest, NextResponse } from "next/server";
import {
  getMarketDataStream,
  startMarketDataStream,
  stopMarketDataStream,
} from "@/lib/services/market-data-stream";

export async function GET() {
  try {
    const stream = getMarketDataStream();
    const status = stream.getStatus();

    return NextResponse.json({
      status: status.isConnected ? "connected" : "disconnected",
      ...status,
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: "Failed to get stream status",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { action, symbols } = body;

    if (!action || !["start", "stop", "add", "remove"].includes(action)) {
      return NextResponse.json(
        {
          error:
            "action must be one of: 'start', 'stop', 'add', 'remove'",
        },
        { status: 400 }
      );
    }

    // ========================================================================
    // START STREAM
    // ========================================================================

    if (action === "start") {
      const stream = startMarketDataStream(
        symbols || ["BTCUSDT", "ETHUSDT"]
      );
      const status = stream.getStatus();

      return NextResponse.json({
        success: true,
        message: "Market data stream started",
        status,
      });
    }

    // ========================================================================
    // STOP STREAM
    // ========================================================================

    if (action === "stop") {
      stopMarketDataStream();

      return NextResponse.json({
        success: true,
        message: "Market data stream stopped",
      });
    }

    // ========================================================================
    // ADD SYMBOLS
    // ========================================================================

    if (action === "add") {
      if (!symbols || !Array.isArray(symbols) || symbols.length === 0) {
        return NextResponse.json(
          { error: "symbols array is required for 'add' action" },
          { status: 400 }
        );
      }

      const stream = getMarketDataStream();
      stream.addSymbols(symbols);

      return NextResponse.json({
        success: true,
        message: `Added ${symbols.length} symbols to stream`,
        symbols,
      });
    }

    // ========================================================================
    // REMOVE SYMBOLS
    // ========================================================================

    if (action === "remove") {
      if (!symbols || !Array.isArray(symbols) || symbols.length === 0) {
        return NextResponse.json(
          { error: "symbols array is required for 'remove' action" },
          { status: 400 }
        );
      }

      const stream = getMarketDataStream();
      stream.removeSymbols(symbols);

      return NextResponse.json({
        success: true,
        message: `Removed ${symbols.length} symbols from stream`,
        symbols,
      });
    }

    return NextResponse.json(
      { error: "Invalid action" },
      { status: 400 }
    );
  } catch (error) {
    console.error("Error in POST /api/market-data/stream:", error);
    return NextResponse.json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
