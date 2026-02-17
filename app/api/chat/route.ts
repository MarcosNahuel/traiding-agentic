/**
 * POST /api/chat - Chat with AI about trading research
 *
 * Uses RAG (Retrieval Augmented Generation) to answer questions
 * based on the research papers and strategies in the database.
 */

import { NextRequest, NextResponse } from "next/server";
import { chat } from "@/lib/agents/chat-agent";
import { createServerClient } from "@/lib/supabase";

export const maxDuration = 60; // 60 seconds for LLM response

export async function POST(req: NextRequest) {
  try {
    // Check if body exists
    const text = await req.text();
    if (!text) {
      return NextResponse.json(
        { error: "Request body is empty" },
        { status: 400 }
      );
    }

    let body;
    try {
      body = JSON.parse(text);
    } catch (e) {
      return NextResponse.json(
        { error: "Invalid JSON in request body" },
        { status: 400 }
      );
    }

    const { message, conversationId } = body;

    if (!message || typeof message !== "string") {
      return NextResponse.json(
        { error: "message is required and must be a string" },
        { status: 400 }
      );
    }

    // Execute chat agent
    const response = await chat({ message });

    // Store conversation in database
    const supabase = createServerClient();

    await supabase.from("chat_history").insert({
      conversation_id: conversationId || null,
      user_message: message,
      assistant_message: response.answer,
      sources_used: response.sources,
      tokens_used: response.tokensUsed,
      created_at: new Date().toISOString(),
    });

    return NextResponse.json({
      answer: response.answer,
      sources: response.sources,
      tokensUsed: response.tokensUsed,
      cost: response.cost,
      conversationId: conversationId || null,
    });
  } catch (error) {
    console.error("Error in POST /api/chat:", error);
    return NextResponse.json(
      {
        error: "Failed to process chat request",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
