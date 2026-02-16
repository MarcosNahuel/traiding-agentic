/**
 * GET /api/pipeline/status - Get current pipeline status
 *
 * Returns statistics about the research pipeline:
 * - Sources pending evaluation
 * - Sources pending extraction
 * - Available strategies
 * - Current guide status
 */

import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET(req: NextRequest) {
  try {
    const supabase = createServerClient();

    // Get sources statistics
    const { data: sourcesStats } = await supabase
      .from("sources")
      .select("status");

    const sourcesByStatus = {
      pending: 0,
      evaluating: 0,
      approved: 0,
      rejected: 0,
      error: 0,
    };

    sourcesStats?.forEach((s: any) => {
      if (sourcesByStatus.hasOwnProperty(s.status)) {
        sourcesByStatus[s.status as keyof typeof sourcesByStatus]++;
      }
    });

    // Get sources pending extraction
    const { count: pendingExtraction } = await supabase
      .from("sources")
      .select("id", { count: "exact", head: true })
      .eq("status", "approved")
      .is("extracted_at", null);

    // Get strategies count
    const { count: strategiesCount } = await supabase
      .from("strategies_found")
      .select("id", { count: "exact", head: true });

    // Get validated strategies count
    const { count: validatedStrategiesCount } = await supabase
      .from("strategies_found")
      .select("id", { count: "exact", head: true })
      .eq("validation_status", "validated");

    // Get current guide info
    const { data: currentGuide } = await supabase
      .from("synthesis_results")
      .select("id, version, based_on_sources, based_on_strategies, created_at")
      .eq("status", "active")
      .order("created_at", { ascending: false })
      .limit(1)
      .single();

    // Get total guides count
    const { count: totalGuides } = await supabase
      .from("synthesis_results")
      .select("id", { count: "exact", head: true });

    return NextResponse.json({
      sources: {
        total: sourcesStats?.length || 0,
        by_status: sourcesByStatus,
        pending_extraction: pendingExtraction || 0,
      },
      strategies: {
        total: strategiesCount || 0,
        validated: validatedStrategiesCount || 0,
      },
      guides: {
        total: totalGuides || 0,
        current: currentGuide || null,
      },
      pipeline_health: {
        ready_to_evaluate: sourcesByStatus.pending > 0,
        ready_to_extract: (pendingExtraction || 0) > 0,
        ready_to_synthesize:
          (strategiesCount || 0) >= 5 &&
          (!currentGuide ||
            (currentGuide.based_on_strategies || 0) < (strategiesCount || 0)),
      },
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error("Error in GET /api/pipeline/status:", error);
    return NextResponse.json(
      {
        error: "Failed to fetch pipeline status",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
