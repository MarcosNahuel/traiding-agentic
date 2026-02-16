/**
 * POST /api/sources/[id]/evaluate - Manually trigger source evaluation
 */

import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";
import { evaluateSource } from "@/lib/agents/source-agent";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const supabase = createServerClient();

    // Get source from DB
    const { data: source, error } = await supabase
      .from("sources")
      .select("*")
      .eq("id", id)
      .single();

    if (error || !source) {
      return NextResponse.json({ error: "Source not found" }, { status: 404 });
    }

    // Check if we have raw content
    if (!source.raw_content) {
      return NextResponse.json(
        { error: "Source has no content to evaluate. Fetch content first." },
        { status: 400 }
      );
    }

    // Check if already evaluated
    if (source.status === "approved" || source.status === "rejected") {
      return NextResponse.json(
        {
          warning: "Source already evaluated",
          currentStatus: source.status,
          overallScore: source.overall_score,
        },
        { status: 200 }
      );
    }

    // Trigger evaluation
    const evaluation = await evaluateSource({
      sourceId: id,
      url: source.url,
      rawContent: source.raw_content,
      sourceType: source.source_type,
    });

    return NextResponse.json({
      success: true,
      evaluation,
    });
  } catch (error) {
    console.error("Error in POST /api/sources/[id]/evaluate:", error);
    return NextResponse.json(
      {
        error: "Failed to evaluate source",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
