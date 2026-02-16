/**
 * Source Agent - Evaluates quality and relevance of trading sources
 */

import { generateObject } from "ai";
import { z } from "zod";
import { google } from "@/lib/ai";
import { SOURCE_AGENT_PROMPT } from "./prompts";
import { createServerClient } from "@/lib/supabase";

// Zod schema for source evaluation
export const sourceEvaluationSchema = z.object({
  title: z.string().describe("Title of the paper/article"),
  authors: z.string().optional().describe("Authors of the paper"),
  publication_year: z.number().optional().describe("Year of publication"),
  relevance_score: z
    .number()
    .min(1)
    .max(10)
    .describe("Relevance to BTC trading (1-10)"),
  credibility_score: z
    .number()
    .min(1)
    .max(10)
    .describe("Source credibility (1-10)"),
  applicability_score: z
    .number()
    .min(1)
    .max(10)
    .describe("Applicability to our context (1-10)"),
  overall_score: z
    .number()
    .min(1)
    .max(10)
    .describe("Overall weighted score (1-10)"),
  tags: z
    .array(z.string())
    .describe("Relevant tags (e.g., momentum, btc, rsi)"),
  summary: z.string().describe("2-3 sentence summary of the content"),
  evaluation_reasoning: z
    .string()
    .describe("Explanation of why these scores were given"),
  decision: z
    .enum(["approved", "rejected"])
    .describe("Approve if overall >= 6, reject otherwise"),
  rejection_reason: z
    .string()
    .nullable()
    .describe("Reason for rejection if decision is rejected"),
});

export type SourceEvaluation = z.infer<typeof sourceEvaluationSchema>;

interface EvaluateSourceParams {
  sourceId: string;
  url: string;
  rawContent: string;
  sourceType: "paper" | "article" | "repo" | "book" | "video";
}

export async function evaluateSource({
  sourceId,
  url,
  rawContent,
  sourceType,
}: EvaluateSourceParams): Promise<SourceEvaluation> {
  const supabase = createServerClient();

  // Log start
  await logAgentAction({
    agent_name: "source",
    action: "evaluate_source",
    source_id: sourceId,
    input_summary: `Evaluating ${sourceType}: ${url}`,
    status: "started",
  });

  const startTime = Date.now();

  try {
    // Update status to evaluating
    await supabase
      .from("sources")
      .update({ status: "evaluating", updated_at: new Date().toISOString() })
      .eq("id", sourceId);

    // Generate evaluation with Gemini
    const result = await generateObject({
      model: google("gemini-2.5-flash"),
      schema: sourceEvaluationSchema,
      system: SOURCE_AGENT_PROMPT,
      prompt: `Evalúa esta fuente de trading:

URL: ${url}
Tipo: ${sourceType}

Contenido:
${rawContent.slice(0, 15000)}${rawContent.length > 15000 ? "\n\n[Contenido truncado]" : ""}`,
    });

    const evaluation = result.object;
    const duration = Date.now() - startTime;

    // Calculate token usage
    const tokensUsed = (result.usage?.totalTokens || 0);

    // Update source in DB with evaluation results
    const newStatus = evaluation.decision === "approved" ? "approved" : "rejected";

    const { error: updateError } = await supabase
      .from("sources")
      .update({
        title: evaluation.title,
        authors: evaluation.authors,
        publication_year: evaluation.publication_year,
        relevance_score: evaluation.relevance_score,
        credibility_score: evaluation.credibility_score,
        applicability_score: evaluation.applicability_score,
        overall_score: evaluation.overall_score,
        tags: evaluation.tags,
        summary: evaluation.summary,
        evaluation_reasoning: evaluation.evaluation_reasoning,
        status: newStatus,
        rejection_reason: evaluation.rejection_reason,
        evaluated_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq("id", sourceId);

    if (updateError) {
      console.error("Failed to update source with evaluation:", updateError);
      throw updateError;
    }

    // Log success
    await logAgentAction({
      agent_name: "source",
      action: "evaluate_source",
      source_id: sourceId,
      input_summary: `${sourceType}: ${url}`,
      output_summary: `Score: ${evaluation.overall_score}/10, Decision: ${evaluation.decision}`,
      reasoning: evaluation.evaluation_reasoning,
      tokens_input: null,
      tokens_output: null,
      tokens_used: tokensUsed,
      duration_ms: duration,
      model_used: "gemini-2.5-flash",
      estimated_cost_usd: calculateCost(tokensUsed),
      status: "success",
    });

    return evaluation;
  } catch (error) {
    const duration = Date.now() - startTime;
    const errorMessage = error instanceof Error ? error.message : String(error);

    // Update source with error status
    await supabase
      .from("sources")
      .update({
        status: "error",
        error_message: errorMessage,
        updated_at: new Date().toISOString(),
      })
      .eq("id", sourceId);

    // Log error
    await logAgentAction({
      agent_name: "source",
      action: "evaluate_source",
      source_id: sourceId,
      input_summary: `${sourceType}: ${url}`,
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
// Gemini 2.5 Flash: $0.075/1M input tokens, $0.30/1M output tokens (approximate)
function calculateCost(totalTokens: number): number {
  // Conservative estimate: assume 50/50 input/output split
  const inputTokens = totalTokens * 0.5;
  const outputTokens = totalTokens * 0.5;

  const inputCost = (inputTokens / 1_000_000) * 0.075;
  const outputCost = (outputTokens / 1_000_000) * 0.3;

  return inputCost + outputCost;
}
