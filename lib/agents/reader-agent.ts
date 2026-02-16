/**
 * Reader Agent - Extracts trading strategies and insights from approved papers
 */

import { generateObject } from "ai";
import { z } from "zod";
import { google } from "@/lib/ai";
import { READER_AGENT_PROMPT } from "./prompts";
import { createServerClient } from "@/lib/supabase";
import { checkAndTriggerSynthesis } from "@/lib/services/auto-synthesis";

// Zod schema for individual strategy
const strategySchema = z.object({
  name: z.string().describe("Descriptive name of the strategy"),
  description: z.string().describe("Brief description of what the strategy does"),
  strategy_type: z
    .enum([
      "momentum",
      "mean_reversion",
      "breakout",
      "trend_following",
      "statistical_arbitrage",
      "market_making",
      "sentiment",
      "machine_learning",
      "hybrid",
      "other",
    ])
    .describe("Type of strategy"),
  market: z.string().default("btc").describe("Market/asset (btc, eth, etc)"),
  timeframe: z
    .string()
    .optional()
    .describe("Recommended timeframe (1h, 4h, 1d, etc)"),
  indicators: z
    .array(z.string())
    .describe(
      "List of indicators with parameters (e.g., 'RSI(14)', 'MACD(12,26,9)')"
    ),
  entry_rules: z.array(z.string()).describe("Specific entry rules"),
  exit_rules: z
    .array(z.string())
    .describe("Specific exit rules (stop-loss, take-profit, trailing)"),
  position_sizing: z
    .string()
    .optional()
    .describe("Position sizing rule if mentioned"),
  backtest_results: z
    .object({
      sharpe_ratio: z.number().optional(),
      max_drawdown: z.number().optional(),
      win_rate: z.number().optional(),
      period: z.string().optional(),
      sample_size: z.string().optional(),
    })
    .optional()
    .describe("Backtest results if available"),
  limitations: z.array(z.string()).describe("Known limitations of the strategy"),
  best_market_conditions: z
    .array(z.string())
    .optional()
    .describe("When strategy works best"),
  worst_market_conditions: z
    .array(z.string())
    .optional()
    .describe("When strategy doesn't work"),
  confidence: z
    .number()
    .min(1)
    .max(10)
    .describe("Confidence in implementation details (1-10)"),
  evidence_strength: z
    .enum(["weak", "moderate", "strong"])
    .describe("Strength of evidence for this strategy"),
});

// Zod schema for complete paper extraction
const paperExtractionSchema = z.object({
  strategies: z
    .array(strategySchema)
    .describe("All trading strategies found in the paper"),
  key_insights: z
    .array(z.string())
    .describe("Important insights that aren't full strategies"),
  risk_warnings: z
    .array(z.string())
    .describe("Specific risks mentioned in the paper"),
  market_conditions: z
    .array(z.string())
    .optional()
    .describe("Market conditions discussed"),
  data_period: z
    .string()
    .optional()
    .describe("Period of data used in the paper"),
  sample_size: z
    .string()
    .optional()
    .describe("Sample size (number of trades, years, etc)"),
  contradicts: z
    .array(
      z.object({
        finding: z.string(),
        source: z.string().optional(),
      })
    )
    .optional()
    .describe("Findings that contradict other research"),
  supports: z
    .array(
      z.object({
        finding: z.string(),
        source: z.string().optional(),
      })
    )
    .optional()
    .describe("Findings that support other research"),
  raw_summary: z.string().describe("Raw summary of all findings"),
  executive_summary: z
    .string()
    .describe("Executive summary (2-3 sentences)"),
  confidence_score: z
    .number()
    .min(1)
    .max(10)
    .describe("Overall confidence in extraction quality"),
});

export type PaperExtraction = z.infer<typeof paperExtractionSchema>;
export type Strategy = z.infer<typeof strategySchema>;

interface ExtractPaperParams {
  sourceId: string;
  title: string;
  rawContent: string;
}

export async function extractPaper({
  sourceId,
  title,
  rawContent,
}: ExtractPaperParams): Promise<PaperExtraction> {
  const supabase = createServerClient();

  // Log start
  await logAgentAction({
    agent_name: "reader",
    action: "extract_paper",
    source_id: sourceId,
    input_summary: `Extracting strategies from: ${title}`,
    status: "started",
  });

  const startTime = Date.now();

  try {
    // Update source status
    await supabase
      .from("sources")
      .update({ status: "processing", updated_at: new Date().toISOString() })
      .eq("id", sourceId);

    // Extract with Gemini
    const result = await generateObject({
      model: google("gemini-2.5-flash"),
      schema: paperExtractionSchema,
      system: READER_AGENT_PROMPT,
      prompt: `Extrae estrategias y hallazgos de este paper:

Título: ${title}

Contenido:
${rawContent.slice(0, 30000)}${rawContent.length > 30000 ? "\n\n[Contenido truncado]" : ""}`,
    });

    const extraction = result.object;
    const duration = Date.now() - startTime;
    const tokensUsed =
      (result.usage?.totalTokens || 0);

    // Insert extraction into database
    const { data: extractionRecord, error: extractionError } = await supabase
      .from("paper_extractions")
      .insert({
        source_id: sourceId,
        strategies: extraction.strategies,
        key_insights: extraction.key_insights,
        risk_warnings: extraction.risk_warnings,
        market_conditions: extraction.market_conditions,
        data_period: extraction.data_period,
        sample_size: extraction.sample_size,
        contradicts: extraction.contradicts,
        supports: extraction.supports,
        raw_summary: extraction.raw_summary,
        executive_summary: extraction.executive_summary,
        confidence_score: extraction.confidence_score,
        processing_model: "gemini-2.5-flash",
        processing_tokens: tokensUsed,
      })
      .select("id")
      .single();

    if (extractionError || !extractionRecord) {
      throw new Error(
        `Failed to insert extraction: ${extractionError?.message}`
      );
    }

    // Insert each strategy as separate record
    for (const strategy of extraction.strategies) {
      const { error: strategyError } = await supabase
        .from("strategies_found")
        .insert({
          source_id: sourceId,
          extraction_id: extractionRecord.id,
          name: strategy.name,
          description: strategy.description,
          strategy_type: strategy.strategy_type,
          market: strategy.market,
          timeframe: strategy.timeframe,
          indicators: strategy.indicators,
          entry_rules: strategy.entry_rules,
          exit_rules: strategy.exit_rules,
          position_sizing: strategy.position_sizing,
          backtest_results: strategy.backtest_results,
          limitations: strategy.limitations,
          best_market_conditions: strategy.best_market_conditions,
          worst_market_conditions: strategy.worst_market_conditions,
          confidence: strategy.confidence,
          evidence_strength: strategy.evidence_strength,
        });

      if (strategyError) {
        console.error(
          `Failed to insert strategy "${strategy.name}":`,
          strategyError
        );
      }
    }

    // Update source status to processed
    const { error: updateError } = await supabase
      .from("sources")
      .update({
        status: "processed",
        updated_at: new Date().toISOString(),
      })
      .eq("id", sourceId);

    if (updateError) {
      console.error("Failed to update source status:", updateError);
    }

    // Log success
    await logAgentAction({
      agent_name: "reader",
      action: "extract_paper",
      source_id: sourceId,
      input_summary: `Paper: ${title}`,
      output_summary: `Found ${extraction.strategies.length} strategies, ${extraction.key_insights.length} insights`,
      reasoning: extraction.executive_summary,
      tokens_input: null,
      tokens_output: null,
      tokens_used: tokensUsed,
      duration_ms: duration,
      model_used: "gemini-2.5-flash",
      estimated_cost_usd: calculateCost(tokensUsed),
      status: "success",
    });

    // Check if synthesis should be auto-triggered
    // This runs in the background without blocking the response
    checkAndTriggerSynthesis().catch((error) => {
      console.error("Auto-synthesis check failed:", error);
    });

    return extraction;
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
      agent_name: "reader",
      action: "extract_paper",
      source_id: sourceId,
      input_summary: `Paper: ${title}`,
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
