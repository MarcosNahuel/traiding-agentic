/**
 * POST /api/pipeline/run - Trigger the full research pipeline
 *
 * Runs the complete research pipeline:
 * 1. Fetch pending sources
 * 2. Evaluate with Source Agent
 * 3. Extract strategies with Reader Agent
 * 4. Synthesize guide with Synthesis Agent
 */

import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export const maxDuration = 300; // 5 minutes for full pipeline

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { mode = "full" } = body; // full, evaluate-only, extract-only, synthesize-only

    const supabase = createServerClient();
    const results: any = {
      mode,
      started_at: new Date().toISOString(),
      steps: [],
    };

    // ========================================================================
    // Step 1: Evaluate pending sources (if mode allows)
    // ========================================================================
    if (mode === "full" || mode === "evaluate-only") {
      const { data: pendingSources, error: fetchError } = await supabase
        .from("sources")
        .select("id, url")
        .eq("status", "pending")
        .limit(10);

      if (!fetchError && pendingSources && pendingSources.length > 0) {
        results.steps.push({
          step: "evaluate_sources",
          count: pendingSources.length,
          sources: pendingSources.map((s: any) => s.id),
        });

        // Trigger evaluation for each source
        for (const source of pendingSources) {
          try {
            await fetch(
              `${req.nextUrl.origin}/api/sources/${source.id}/evaluate`,
              { method: "POST" }
            );
          } catch (error) {
            console.error(`Failed to evaluate source ${source.id}:`, error);
          }
        }
      } else {
        results.steps.push({
          step: "evaluate_sources",
          count: 0,
          message: "No pending sources to evaluate",
        });
      }
    }

    // ========================================================================
    // Step 2: Extract strategies from approved sources (if mode allows)
    // ========================================================================
    if (mode === "full" || mode === "extract-only") {
      const { data: approvedSources, error: fetchError } = await supabase
        .from("sources")
        .select("id")
        .eq("status", "approved")
        .is("extracted_at", null)
        .limit(5);

      if (!fetchError && approvedSources && approvedSources.length > 0) {
        results.steps.push({
          step: "extract_strategies",
          count: approvedSources.length,
          sources: approvedSources.map((s: any) => s.id),
        });

        // Trigger extraction for each source
        for (const source of approvedSources) {
          try {
            await fetch(
              `${req.nextUrl.origin}/api/sources/${source.id}/extract`,
              { method: "POST" }
            );
          } catch (error) {
            console.error(`Failed to extract from source ${source.id}:`, error);
          }
        }
      } else {
        results.steps.push({
          step: "extract_strategies",
          count: 0,
          message: "No approved sources pending extraction",
        });
      }
    }

    // ========================================================================
    // Step 3: Synthesize guide (if mode allows)
    // ========================================================================
    if (mode === "full" || mode === "synthesize-only") {
      try {
        const synthesisResponse = await fetch(
          `${req.nextUrl.origin}/api/guides/synthesize`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
          }
        );

        const synthesisData = await synthesisResponse.json();

        results.steps.push({
          step: "synthesize_guide",
          success: synthesisResponse.ok,
          data: synthesisData,
        });
      } catch (error) {
        results.steps.push({
          step: "synthesize_guide",
          success: false,
          error:
            error instanceof Error ? error.message : "Synthesis failed",
        });
      }
    }

    results.completed_at = new Date().toISOString();
    results.duration_ms =
      new Date(results.completed_at).getTime() -
      new Date(results.started_at).getTime();

    return NextResponse.json({
      success: true,
      message: "Pipeline execution completed",
      results,
    });
  } catch (error) {
    console.error("Error in POST /api/pipeline/run:", error);
    return NextResponse.json(
      {
        error: "Pipeline execution failed",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
