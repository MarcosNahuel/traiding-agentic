/**
 * GET /api/strategist/latest - último informe diario de Claude (el Daily Strategist).
 * Se persiste en llm_audit_reports (model_used = claude-*).
 */

import { NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET() {
  try {
    const supabase = createServerClient();

    const { data, error } = await supabase
      .from("llm_audit_reports")
      .select("performance_summary, market_events, recommendations, overall_grade, created_at")
      .ilike("model_used", "claude%")
      .order("created_at", { ascending: false })
      .limit(1);

    if (error) {
      return NextResponse.json(
        { error: "Failed to fetch strategist report", details: error.message },
        { status: 500 }
      );
    }

    const row = data?.[0];
    if (!row) return NextResponse.json({ report: null });

    const ps = (row.performance_summary ?? {}) as Record<string, unknown>;
    const report = {
      decision: ps.decision ?? row.overall_grade ?? "",
      confidence: ps.confidence ?? 0,
      summary: ps.summary ?? "",
      macro_context: ps.macro_context ?? row.market_events ?? "",
      performance_review: ps.performance_review ?? "",
      evidence: ps.evidence ?? row.recommendations ?? [],
      risks: ps.risks ?? "",
      created_at: row.created_at,
    };

    return NextResponse.json({ report });
  } catch (err) {
    return NextResponse.json(
      { error: "Internal server error", details: err instanceof Error ? err.message : String(err) },
      { status: 500 }
    );
  }
}
