/**
 * GET /api/guides/history - Get historical trading guides
 *
 * Returns all synthesis results (guides) ordered by version/date.
 */

import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const limit = parseInt(searchParams.get("limit") || "10");
    const offset = parseInt(searchParams.get("offset") || "0");
    const status = searchParams.get("status"); // active, superseded, archived

    const supabase = createServerClient();

    let query = supabase
      .from("synthesis_results")
      .select("*", { count: "exact" })
      .order("version", { ascending: false })
      .range(offset, offset + limit - 1);

    // Filter by status if provided
    if (status && ["active", "superseded", "archived"].includes(status)) {
      query = query.eq("status", status);
    }

    const { data, error, count } = await query;

    if (error) {
      return NextResponse.json(
        { error: "Failed to fetch guide history", details: error.message },
        { status: 500 }
      );
    }

    return NextResponse.json({
      guides: data || [],
      total: count || 0,
      limit,
      offset,
    });
  } catch (error) {
    console.error("Error in GET /api/guides/history:", error);
    return NextResponse.json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
