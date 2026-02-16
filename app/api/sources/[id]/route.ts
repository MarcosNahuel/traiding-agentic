/**
 * GET /api/sources/[id] - Get source details
 */

import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const supabase = createServerClient();

    const { data: source, error } = await supabase
      .from("sources")
      .select("*")
      .eq("id", id)
      .single();

    if (error || !source) {
      return NextResponse.json({ error: "Source not found" }, { status: 404 });
    }

    return NextResponse.json({ source });
  } catch (error) {
    console.error("Error in GET /api/sources/[id]:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
