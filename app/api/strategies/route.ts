/**
 * API Route: GET /api/strategies
 * Lists all strategies found from extractions
 */

import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET(req: NextRequest) {
  const supabase = createServerClient();
  const searchParams = req.nextUrl.searchParams;

  // Query parameters
  const sourceId = searchParams.get("source_id");
  const extractionId = searchParams.get("extraction_id");
  const strategyType = searchParams.get("strategy_type");
  const minConfidence = searchParams.get("min_confidence");

  let query = supabase
    .from("strategies_found")
    .select(
      `
      *,
      source:sources(id, url, title, authors, publication_year),
      extraction:paper_extractions(id, confidence_score, executive_summary)
    `
    )
    .order("created_at", { ascending: false });

  // Apply filters
  if (sourceId) {
    query = query.eq("source_id", sourceId);
  }

  if (extractionId) {
    query = query.eq("extraction_id", extractionId);
  }

  if (strategyType) {
    query = query.eq("strategy_type", strategyType);
  }

  if (minConfidence) {
    query = query.gte("confidence", parseInt(minConfidence));
  }

  const { data: strategies, error } = await query;

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ strategies });
}
