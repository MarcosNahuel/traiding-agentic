/**
 * API Route: GET /api/guides
 * Lists all trading guides
 */

import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET(req: NextRequest) {
  const supabase = createServerClient();
  const searchParams = req.nextUrl.searchParams;
  const version = searchParams.get("version");
  const latest = searchParams.get("latest") === "true";

  let query = supabase
    .from("trading_guides")
    .select("*")
    .order("version", { ascending: false });

  if (version) {
    query = query.eq("version", parseInt(version));
  } else if (latest) {
    query = query.limit(1);
  }

  const { data: guides, error } = await query;

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  // If latest=true and single guide found, return as object instead of array
  if (latest && guides && guides.length === 1) {
    return NextResponse.json({ guide: guides[0] });
  }

  return NextResponse.json({ guides });
}
