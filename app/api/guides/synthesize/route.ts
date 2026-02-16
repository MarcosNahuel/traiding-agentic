/**
 * API Route: POST /api/guides/synthesize
 * Generates a new trading guide from all strategies
 */

import { NextRequest, NextResponse } from "next/server";
import { synthesizeGuide } from "@/lib/agents/synthesis-agent";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const {
      minConfidence = 6,
      minEvidenceStrength = "moderate",
      strategyTypes,
    } = body;

    // Validate parameters
    if (minConfidence < 1 || minConfidence > 10) {
      return NextResponse.json(
        { error: "minConfidence must be between 1 and 10" },
        { status: 400 }
      );
    }

    if (!["weak", "moderate", "strong"].includes(minEvidenceStrength)) {
      return NextResponse.json(
        { error: "minEvidenceStrength must be weak, moderate, or strong" },
        { status: 400 }
      );
    }

    // Synthesize in background (don't await to return quickly)
    synthesizeInBackground({
      minConfidence,
      minEvidenceStrength,
      strategyTypes,
    }).catch((error) => {
      console.error("Background synthesis failed:", error);
    });

    return NextResponse.json({
      success: true,
      message: "Guide synthesis started",
      params: { minConfidence, minEvidenceStrength, strategyTypes },
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

// Background synthesis function
async function synthesizeInBackground(params: {
  minConfidence: number;
  minEvidenceStrength: "weak" | "moderate" | "strong";
  strategyTypes?: string[];
}): Promise<void> {
  try {
    await synthesizeGuide(params);
  } catch (error) {
    console.error("Failed to synthesize guide:", error);
    throw error;
  }
}
