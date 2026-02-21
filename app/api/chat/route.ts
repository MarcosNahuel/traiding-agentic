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
const CHAT_PROVIDER_TIMEOUT_MS = 12000;
const CHAT_PERSIST_TIMEOUT_MS = 5000;

function buildFallbackAnswer(message: string): string {
  return [
    "No pude consultar el modelo de IA en este momento, pero el chat sigue operativo en modo degradado.",
    "Causa probable: credencial del proveedor no valida o temporalmente bloqueada.",
    "",
    `Tu pregunta fue: "${message}"`,
    "",
    "Accion recomendada: rotar la API key de Gemini y reintentar.",
  ].join("\n");
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error(`${label} timeout after ${timeoutMs}ms`)),
      timeoutMs
    );
    promise
      .then((value) => {
        clearTimeout(timer);
        resolve(value);
      })
      .catch((error) => {
        clearTimeout(timer);
        reject(error);
      });
  });
}

export async function POST(req: NextRequest) {
  let message = "";
  let conversationId: string | null = null;

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

    message = String(body.message ?? "");
    conversationId =
      typeof body.conversationId === "string" ? body.conversationId : null;

    if (!message || typeof message !== "string") {
      return NextResponse.json(
        { error: "message is required and must be a string" },
        { status: 400 }
      );
    }

    let response:
      | {
          answer: string;
          sources: unknown[];
          tokensUsed: number;
          cost: number;
        }
      | undefined;
    let fallback = false;
    let fallbackReason: string | null = null;

    try {
      response = await withTimeout(
        chat({ message }),
        CHAT_PROVIDER_TIMEOUT_MS,
        "chat_provider"
      );
    } catch (chatError) {
      fallback = true;
      fallbackReason =
        chatError instanceof Error ? chatError.message : String(chatError);
      response = {
        answer: buildFallbackAnswer(message),
        sources: [],
        tokensUsed: 0,
        cost: 0,
      };
      console.warn("POST /api/chat running in fallback mode:", fallbackReason);
    }

    // Store conversation in database
    const supabase = createServerClient();

    try {
      await withTimeout(
        Promise.resolve(
          supabase.from("chat_history").insert({
            conversation_id: conversationId,
            user_message: message,
            assistant_message: response.answer,
            sources_used: response.sources,
            tokens_used: response.tokensUsed,
            created_at: new Date().toISOString(),
          })
        ),
        CHAT_PERSIST_TIMEOUT_MS,
        "chat_history_insert"
      );
    } catch (persistError) {
      console.warn(
        "POST /api/chat could not persist chat_history:",
        persistError instanceof Error ? persistError.message : String(persistError)
      );
    }

    return NextResponse.json({
      answer: response.answer,
      sources: response.sources,
      tokensUsed: response.tokensUsed,
      cost: response.cost,
      conversationId,
      fallback,
      ...(fallbackReason ? { fallbackReason } : {}),
    });
  } catch (error) {
    console.error("Error in POST /api/chat:", error);

    // Final safety net: keep endpoint available for UI/automation instead of hard 500.
    const safeAnswer = buildFallbackAnswer(message || "N/A");
    return NextResponse.json({
      answer: safeAnswer,
      sources: [],
      tokensUsed: 0,
      cost: 0,
      conversationId,
      fallback: true,
      fallbackReason: error instanceof Error ? error.message : String(error),
    });
  }
}
