/**
 * API Route: POST /api/sources/:id/extract
 * Extracts strategies from an approved source
 */

import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";
import { extractPaper } from "@/lib/agents/reader-agent";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const supabase = createServerClient();

  // Get source
  const { data: source, error: sourceError } = await supabase
    .from("sources")
    .select("*")
    .eq("id", id)
    .single();

  if (sourceError || !source) {
    return NextResponse.json({ error: "Source not found" }, { status: 404 });
  }

  // Verify source is approved
  if (source.status !== "approved") {
    return NextResponse.json(
      { error: `Source must be approved (current status: ${source.status})` },
      { status: 400 }
    );
  }

  // Verify source has content
  if (!source.raw_content) {
    return NextResponse.json(
      { error: "Source has no content to extract" },
      { status: 400 }
    );
  }

  try {
    // Extract in background (don't await)
    extractInBackground(id, source.title, source.raw_content).catch((error) => {
      console.error("Background extraction failed:", error);
    });

    return NextResponse.json({
      success: true,
      message: "Extraction started",
      sourceId: id,
    });
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error ? error.message : "Unknown error occurred",
      },
      { status: 500 }
    );
  }
}

// Background extraction function
async function extractInBackground(
  sourceId: string,
  title: string,
  rawContent: string
): Promise<void> {
  try {
    await extractPaper({ sourceId, title, rawContent });
  } catch (error) {
    console.error(`Failed to extract source ${sourceId}:`, error);
    throw error;
  }
}
