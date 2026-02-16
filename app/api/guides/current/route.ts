/**
 * GET /api/guides/current - Get the current active trading guide
 *
 * Returns the most recent active synthesis result (trading guide).
 */

import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET(req: NextRequest) {
  try {
    const supabase = createServerClient();

    // Get the most recent active synthesis
    const { data: currentGuide, error } = await supabase
      .from("synthesis_results")
      .select("*")
      .eq("status", "active")
      .order("created_at", { ascending: false })
      .limit(1)
      .single();

    if (error && error.code !== "PGRST116") {
      // PGRST116 = no rows returned
      return NextResponse.json(
        { error: "Failed to fetch current guide", details: error.message },
        { status: 500 }
      );
    }

    if (!currentGuide) {
      return NextResponse.json(
        {
          guide: null,
          message: "No active guide available. Add sources and run synthesis.",
        },
        { status: 200 }
      );
    }

    return NextResponse.json({
      guide: currentGuide,
    });
  } catch (error) {
    console.error("Error in GET /api/guides/current:", error);
    return NextResponse.json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
