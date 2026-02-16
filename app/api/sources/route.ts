/**
 * POST /api/sources - Add a new source for evaluation
 * GET /api/sources - List all sources with optional filtering
 */

import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";
import { safeFetch } from "@/lib/utils/fetcher";
import { evaluateSource } from "@/lib/agents/source-agent";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { url, sourceType } = body;

    // Validate input
    if (!url || typeof url !== "string") {
      return NextResponse.json(
        { error: "URL is required and must be a string" },
        { status: 400 }
      );
    }

    const validTypes = ["paper", "article", "repo", "book", "video"];
    if (!sourceType || !validTypes.includes(sourceType)) {
      return NextResponse.json(
        { error: `sourceType must be one of: ${validTypes.join(", ")}` },
        { status: 400 }
      );
    }

    const supabase = createServerClient();

    // Check if source already exists
    const { data: existing } = await supabase
      .from("sources")
      .select("id, status")
      .eq("url", url)
      .single();

    if (existing) {
      return NextResponse.json(
        {
          error: "Source already exists",
          sourceId: existing.id,
          status: existing.status,
        },
        { status: 409 }
      );
    }

    // Create source in DB
    const { data: source, error: insertError } = await supabase
      .from("sources")
      .insert({
        url,
        source_type: sourceType,
        status: "pending",
      })
      .select("id")
      .single();

    if (insertError) {
      return NextResponse.json(
        { error: "Failed to create source", details: insertError.message },
        { status: 500 }
      );
    }

    // Fetch content in background and trigger evaluation
    // We'll return immediately and process asynchronously
    fetchAndEvaluate(source.id, url, sourceType).catch(console.error);

    return NextResponse.json({
      success: true,
      sourceId: source.id,
      status: "pending",
      message: "Source added, evaluation in progress",
    });
  } catch (error) {
    console.error("Error in POST /api/sources:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const status = searchParams.get("status");
    const sourceType = searchParams.get("type");
    const limit = parseInt(searchParams.get("limit") || "50");
    const offset = parseInt(searchParams.get("offset") || "0");

    const supabase = createServerClient();

    let query = supabase
      .from("sources")
      .select("*", { count: "exact" })
      .order("created_at", { ascending: false })
      .range(offset, offset + limit - 1);

    if (status) {
      query = query.eq("status", status);
    }

    if (sourceType) {
      query = query.eq("source_type", sourceType);
    }

    const { data, error, count } = await query;

    if (error) {
      return NextResponse.json(
        { error: "Failed to fetch sources", details: error.message },
        { status: 500 }
      );
    }

    return NextResponse.json({
      sources: data || [],
      total: count || 0,
      limit,
      offset,
    });
  } catch (error) {
    console.error("Error in GET /api/sources:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}

// Background processing function
async function fetchAndEvaluate(
  sourceId: string,
  url: string,
  sourceType: string
) {
  const supabase = createServerClient();

  try {
    // Update status to fetching
    await supabase
      .from("sources")
      .update({ status: "fetching", updated_at: new Date().toISOString() })
      .eq("id", sourceId);

    // Fetch content using safe fetcher (SSRF protection)
    const result = await safeFetch(url);
    const rawContent = result.content;

    if (!rawContent || rawContent.length < 100) {
      throw new Error("Content too short or empty");
    }

    // Update with raw content
    await supabase
      .from("sources")
      .update({
        raw_content: rawContent.slice(0, 100000), // Store first 100K chars
        content_length: rawContent.length,
        fetched_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq("id", sourceId);

    // Trigger evaluation
    await evaluateSource({
      sourceId,
      url,
      rawContent,
      sourceType: sourceType as "paper" | "article" | "repo" | "book" | "video",
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);

    await supabase
      .from("sources")
      .update({
        status: "error",
        error_message: errorMessage,
        updated_at: new Date().toISOString(),
      })
      .eq("id", sourceId);

    console.error(`Failed to fetch/evaluate source ${sourceId}:`, error);
  }
}
