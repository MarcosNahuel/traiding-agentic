/**
 * Chat Agent - RAG-based Q&A over research papers and trading guides
 */

import { generateText, embed } from "ai";
import { google } from "@/lib/ai";
import { CHAT_AGENT_PROMPT } from "./prompts";
import { createServerClient } from "@/lib/supabase";
import { truncateEmbedding } from "@/lib/utils/embeddings";

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  metadata?: Record<string, unknown>;
}

interface ChatParams {
  message: string;
  conversationHistory?: ChatMessage[];
  includeGuide?: boolean;
  includeStrategies?: boolean;
  maxChunks?: number;
}

interface ChatResponse {
  answer: string;
  sources: Array<{
    type: "paper" | "strategy" | "guide";
    title: string;
    content: string;
    similarity?: number;
  }>;
  tokensUsed: number;
  cost: number;
}

export async function chat(params: ChatParams): Promise<ChatResponse> {
  const supabase = createServerClient();
  const {
    message,
    conversationHistory = [],
    includeGuide = true,
    includeStrategies = true,
    maxChunks = 5,
  } = params;

  // Log start
  await logAgentAction({
    agent_name: "chat",
    action: "answer_question",
    input_summary: message.substring(0, 100),
    status: "started",
  });

  const startTime = Date.now();

  try {
    // 1. Generate embedding for the question
    const { embedding: rawEmbedding } = await embed({
      model: google.embedding("gemini-embedding-001"),
      value: message,
    });

    // Truncate to 1024 dimensions (HNSW index limit is 2000, we use 1024 for compatibility)
    const embedding = truncateEmbedding(rawEmbedding, 1024);

    // 2. Search for relevant paper chunks using vector similarity
    const { data: chunks, error: chunksError } = await supabase.rpc(
      "match_chunks",
      {
        query_embedding: embedding,
        match_threshold: 0.7,
        match_count: maxChunks,
      }
    );

    if (chunksError) {
      console.warn("Failed to fetch chunks:", chunksError);
    }

    // 3. Fetch relevant strategies (high confidence ones)
    let strategies: any[] = [];
    if (includeStrategies) {
      const { data: strats, error: stratsError } = await supabase
        .from("strategies_found")
        .select(
          `
          *,
          source:sources(title, authors, publication_year)
        `
        )
        .gte("confidence", 7)
        .order("confidence", { ascending: false })
        .limit(3);

      if (stratsError) {
        console.warn("Failed to fetch strategies:", stratsError);
      } else {
        strategies = strats || [];
      }
    }

    // 4. Fetch latest trading guide
    let guide: any = null;
    if (includeGuide) {
      const { data: latestGuide, error: guideError } = await supabase
        .from("trading_guides")
        .select("*")
        .order("version", { ascending: false })
        .limit(1)
        .single();

      if (guideError) {
        console.warn("Failed to fetch guide:", guideError);
      } else {
        guide = latestGuide;
      }
    }

    // 5. Build context for LLM
    const contextParts: string[] = [];

    // Add paper chunks
    if (chunks && chunks.length > 0) {
      contextParts.push("## Fragmentos Relevantes de Papers:\n");
      chunks.forEach((chunk: any, idx: number) => {
        contextParts.push(
          `### Fragmento ${idx + 1} (similarity: ${(chunk.similarity * 100).toFixed(1)}%)`
        );
        if (chunk.section_title) {
          contextParts.push(`Sección: ${chunk.section_title}`);
        }
        contextParts.push(`Contenido: ${chunk.content}\n`);
      });
    }

    // Add strategies
    if (strategies.length > 0) {
      contextParts.push("\n## Estrategias Encontradas:\n");
      strategies.forEach((strat: any, idx: number) => {
        contextParts.push(`### Estrategia ${idx + 1}: ${strat.name}`);
        contextParts.push(`Tipo: ${strat.strategy_type}`);
        contextParts.push(`Confianza: ${strat.confidence}/10`);
        contextParts.push(`Evidencia: ${strat.evidence_strength}`);
        if (strat.source) {
          contextParts.push(
            `Fuente: ${strat.source.title} (${strat.source.publication_year || "N/A"})`
          );
        }
        if (strat.description) {
          contextParts.push(`Descripción: ${strat.description}`);
        }
        if (strat.entry_rules && strat.entry_rules.length > 0) {
          contextParts.push(`Reglas de entrada: ${strat.entry_rules.join("; ")}`);
        }
        if (strat.exit_rules && strat.exit_rules.length > 0) {
          contextParts.push(`Reglas de salida: ${strat.exit_rules.join("; ")}`);
        }
        contextParts.push("");
      });
    }

    // Add trading guide
    if (guide) {
      contextParts.push("\n## Guía de Trading Actual:\n");
      contextParts.push(`Versión: ${guide.version}`);
      contextParts.push(`Confianza: ${guide.confidence_score}/10`);
      contextParts.push(
        `Basada en: ${guide.based_on_strategies} estrategias de ${guide.based_on_sources} fuentes`
      );
      contextParts.push(
        `\nResumen: ${guide.executive_summary || "No disponible"}`
      );

      if (guide.primary_strategy) {
        contextParts.push(
          `\nEstrategia Primaria: ${guide.primary_strategy.name}`
        );
        contextParts.push(`Razón: ${guide.primary_strategy.why_primary}`);
      }

      if (guide.market_conditions_map) {
        contextParts.push("\nMapeo de Condiciones:");
        Object.entries(guide.market_conditions_map).forEach(([cond, strat]) => {
          contextParts.push(`  - ${cond}: ${strat}`);
        });
      }
    }

    const context = contextParts.join("\n");

    // 6. Build conversation messages
    const messages = [
      { role: "system" as const, content: CHAT_AGENT_PROMPT },
      ...conversationHistory,
      {
        role: "user" as const,
        content: `Contexto de la base de conocimiento:\n\n${context}\n\n---\n\nPregunta del usuario: ${message}`,
      },
    ];

    // 7. Generate response with Gemini
    const result = await generateText({
      model: google("gemini-2.5-flash"),
      messages,
    });

    const answer = result.text;
    const duration = Date.now() - startTime;
    const tokensUsed =
      (result.usage?.totalTokens || 0);

    // 8. Store conversation in database
    // Note: route.ts also persists via chat_history; this secondary insert is best-effort
    try {
      await supabase.from("chat_history").insert({
        user_message: message,
        assistant_message: answer,
        tokens_used: tokensUsed,
        created_at: new Date().toISOString(),
      });
    } catch (persistErr) {
      console.warn("chat-agent: could not persist chat_history:", persistErr);
    }

    // 9. Build sources array for response
    const sources: ChatResponse["sources"] = [];

    // Add paper chunks as sources
    if (chunks) {
      chunks.forEach((chunk: any) => {
        sources.push({
          type: "paper",
          title: chunk.section_title || "Paper Fragment",
          content: chunk.content.substring(0, 200) + "...",
          similarity: chunk.similarity,
        });
      });
    }

    // Add strategies as sources
    strategies.forEach((strat: any) => {
      sources.push({
        type: "strategy",
        title: `${strat.name} (${strat.source?.title || "Unknown"})`,
        content: strat.description || "No description",
      });
    });

    // Add guide as source
    if (guide) {
      sources.push({
        type: "guide",
        title: `Trading Guide v${guide.version}`,
        content: guide.executive_summary || "No summary available",
      });
    }

    // Log success
    await logAgentAction({
      agent_name: "chat",
      action: "answer_question",
      input_summary: message.substring(0, 100),
      output_summary: answer.substring(0, 150),
      tokens_input: undefined,
      tokens_output: undefined,
      tokens_used: tokensUsed,
      duration_ms: duration,
      model_used: "gemini-2.5-flash",
      estimated_cost_usd: calculateCost(tokensUsed),
      status: "success",
    });

    return {
      answer,
      sources,
      tokensUsed,
      cost: calculateCost(tokensUsed),
    };
  } catch (error) {
    const duration = Date.now() - startTime;
    const errorMessage = error instanceof Error ? error.message : String(error);

    // Log error
    await logAgentAction({
      agent_name: "chat",
      action: "answer_question",
      input_summary: message.substring(0, 100),
      duration_ms: duration,
      status: "error",
      error_message: errorMessage,
    });

    throw error;
  }
}

// Helper to log agent actions
interface LogAgentActionParams {
  agent_name: "source" | "reader" | "synthesis" | "trading" | "chat";
  action: string;
  source_id?: string;
  input_summary?: string;
  output_summary?: string;
  reasoning?: string;
  tokens_input?: number;
  tokens_output?: number;
  tokens_used?: number;
  duration_ms?: number;
  model_used?: string;
  estimated_cost_usd?: number;
  status: "started" | "success" | "error" | "warning";
  error_message?: string;
}

async function logAgentAction(params: LogAgentActionParams): Promise<void> {
  const supabase = createServerClient();

  await supabase.from("agent_logs").insert({
    agent_name: params.agent_name,
    action: params.action,
    source_id: params.source_id || null,
    input_summary: params.input_summary || null,
    output_summary: params.output_summary || null,
    reasoning: params.reasoning || null,
    tokens_input: params.tokens_input || null,
    tokens_output: params.tokens_output || null,
    tokens_used: params.tokens_used || null,
    duration_ms: params.duration_ms || null,
    model_used: params.model_used || null,
    estimated_cost_usd: params.estimated_cost_usd || null,
    status: params.status,
    error_message: params.error_message || null,
  });
}

// Estimate cost based on Gemini pricing
// Gemini 2.5 Flash: $0.075/1M input tokens, $0.30/1M output tokens
function calculateCost(totalTokens: number): number {
  const inputTokens = totalTokens * 0.5;
  const outputTokens = totalTokens * 0.5;

  const inputCost = (inputTokens / 1_000_000) * 0.075;
  const outputCost = (outputTokens / 1_000_000) * 0.3;

  return inputCost + outputCost;
}
