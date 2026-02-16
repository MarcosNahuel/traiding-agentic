/**
 * API Route: GET /api/extractions
 * Lists all paper extractions with their strategies
 */

import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET(req: NextRequest) {
  const supabase = createServerClient();
  const searchParams = req.nextUrl.searchParams;
  const sourceId = searchParams.get("source_id");

  let query = supabase
    .from("paper_extractions")
    .select(
      `
      *,
      source:sources(id, url, title, authors, publication_year, overall_score)
    `
    )
    .order("processed_at", { ascending: false });

  if (sourceId) {
    query = query.eq("source_id", sourceId);
  }

  const { data: extractions, error } = await query;

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ extractions });
}
