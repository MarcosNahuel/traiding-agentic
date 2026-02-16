/**
 * GET /api/risk-events - List risk events with filtering
 */

import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);

    // Query parameters
    const severity = searchParams.get("severity");
    const resolved = searchParams.get("resolved");
    const limit = parseInt(searchParams.get("limit") || "50");
    const offset = parseInt(searchParams.get("offset") || "0");

    const supabase = createServerClient();

    // Build query
    let query = supabase
      .from("risk_events")
      .select("*, positions(symbol), trade_proposals(symbol, type)", {
        count: "exact",
      })
      .order("created_at", { ascending: false })
      .range(offset, offset + limit - 1);

    // Apply filters
    if (severity) {
      query = query.eq("severity", severity);
    }

    if (resolved !== null) {
      query = query.eq("resolved", resolved === "true");
    }

    const { data, error, count } = await query;

    if (error) {
      return NextResponse.json(
        { error: "Failed to fetch risk events", details: error.message },
        { status: 500 }
      );
    }

    // Calculate summary stats
    const summary = {
      total: count || 0,
      critical: data?.filter((e) => e.severity === "critical").length || 0,
      warning: data?.filter((e) => e.severity === "warning").length || 0,
      info: data?.filter((e) => e.severity === "info").length || 0,
      unresolved: data?.filter((e) => !e.resolved).length || 0,
    };

    return NextResponse.json({
      events: data || [],
      total: count || 0,
      limit,
      offset,
      summary,
    });
  } catch (error) {
    console.error("Error in GET /api/risk-events:", error);
    return NextResponse.json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
