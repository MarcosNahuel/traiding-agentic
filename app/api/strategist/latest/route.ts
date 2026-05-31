/**
 * GET /api/strategist/latest - último informe diario de Claude (el Daily Strategist).
 * Se persiste como risk_events(event_type='strategist_report').
 */

import { NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET() {
  try {
    const supabase = createServerClient();

    const { data, error } = await supabase
      .from("risk_events")
      .select("message, details, created_at")
      .eq("event_type", "strategist_report")
      .order("created_at", { ascending: false })
      .limit(1);

    if (error) {
      return NextResponse.json(
        { error: "Failed to fetch strategist report", details: error.message },
        { status: 500 }
      );
    }

    const row = data?.[0];
    const report = row
      ? { ...(row.details ?? {}), created_at: row.created_at }
      : null;

    return NextResponse.json({ report });
  } catch (err) {
    return NextResponse.json(
      { error: "Internal server error", details: err instanceof Error ? err.message : String(err) },
      { status: 500 }
    );
  }
}
