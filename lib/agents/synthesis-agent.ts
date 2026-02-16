/**
 * Synthesis Agent - Combines findings from multiple papers into trading guides
 */

import { generateObject } from "ai";
import { z } from "zod";
import { google } from "@/lib/ai";
import { SYNTHESIS_AGENT_PROMPT } from "./prompts";
import { createServerClient } from "@/lib/supabase";

// Zod schema for ranked strategy
const rankedStrategySchema = z.object({
  strategy_id: z.string().describe("ID of the strategy"),
  name: z.string().describe("Strategy name"),
  rank: z.number().describe("Rank position (1 = best)"),
  evidence_score: z
    .number()
    .min(1)
    .max(10)
    .describe("Overall evidence quality (1-10)"),
  reasoning: z.string().describe("Why this strategy was ranked here"),
  sources_count: z.number().describe("Number of sources supporting this"),
  recommended: z.boolean().describe("Whether to recommend this strategy"),
});

// Zod schema for synthesis output
const synthesisSchema = z.object({
  primary_strategy: z.object({
    name: z.string(),
    description: z.string(),
    why_primary: z.string(),
    evidence_score: z.number().min(1).max(10),
    sources_count: z.number(),
  }),
  secondary_strategies: z
    .array(
      z.object({
        name: z.string(),
        description: z.string(),
        use_case: z.string().describe("When to use this strategy"),
        evidence_score: z.number().min(1).max(10),
      })
    )
    .describe("Alternative strategies to consider"),
  market_conditions_map: z
    .object({
      trending_up: z.string().describe("Best strategies for uptrend"),
      trending_down: z.string().describe("Best strategies for downtrend"),
      ranging: z.string().describe("Best strategies for sideways market"),
      high_volatility: z.string().describe("Best strategies for high vol"),
      low_volatility: z.string().describe("Best strategies for low vol"),
    })
    .describe("Strategy recommendations per market condition"),
  avoid_list: z
    .array(z.string())
    .describe("Strategies to avoid and why (brief)"),
  common_patterns: z
    .array(z.string())
    .describe("Patterns found across multiple papers"),
  contradictions_resolved: z
    .array(
      z.object({
        topic: z.string(),
        conflict: z.string(),
        resolution: z.string(),
      })
    )
    .describe("How contradictions between papers were resolved"),
  risk_parameters: z.object({
    max_position_size: z.string(),
    stop_loss_approach: z.string(),
    take_profit_approach: z.string(),
    max_leverage: z.string(),
    max_drawdown_tolerance: z.string(),
  }),
  executive_summary: z
    .string()
    .describe("3-5 sentence summary of the guide"),
  confidence_score: z
    .number()
    .min(1)
    .max(10)
    .describe("Overall confidence in this synthesis"),
  limitations: z
    .array(z.string())
    .describe("Known limitations of this guide"),
  full_guide_markdown: z
    .string()
    .describe("Complete trading guide in markdown format"),
});

export type Synthesis = z.infer<typeof synthesisSchema>;

interface SynthesizeParams {
  minConfidence?: number;
  minEvidenceStrength?: "weak" | "moderate" | "strong";
  strategyTypes?: string[];
}

export async function synthesizeGuide(
  params: SynthesizeParams = {}
): Promise<Synthesis> {
  const supabase = createServerClient();
  const {
    minConfidence = 6,
    minEvidenceStrength = "moderate",
    strategyTypes,
  } = params;

  // Log start
  await logAgentAction({
    agent_name: "synthesis",
    action: "synthesize_guide",
    input_summary: `Creating guide with minConfidence=${minConfidence}, minEvidence=${minEvidenceStrength}`,
    status: "started",
  });

  const startTime = Date.now();

  try {
    // Fetch all strategies with their sources
    let strategiesQuery = supabase
      .from("strategies_found")
      .select(
        `
        *,
        source:sources(id, url, title, authors, publication_year, overall_score, credibility_score),
        extraction:paper_extractions(confidence_score, executive_summary, key_insights, risk_warnings)
      `
      )
      .gte("confidence", minConfidence)
      .order("confidence", { ascending: false });

    // Filter by evidence strength
    const evidenceOrder = { weak: 1, moderate: 2, strong: 3 };
    const minEvidenceLevel = evidenceOrder[minEvidenceStrength];
    if (minEvidenceLevel >= 2) {
      strategiesQuery = strategiesQuery.in("evidence_strength", [
        "moderate",
        "strong",
      ]);
    }
    if (minEvidenceLevel >= 3) {
      strategiesQuery = strategiesQuery.eq("evidence_strength", "strong");
    }

    // Filter by strategy types if specified
    if (strategyTypes && strategyTypes.length > 0) {
      strategiesQuery = strategiesQuery.in("strategy_type", strategyTypes);
    }

    const { data: strategies, error: strategiesError } =
      await strategiesQuery;

    if (strategiesError) {
      throw new Error(`Failed to fetch strategies: ${strategiesError.message}`);
    }

    if (!strategies || strategies.length === 0) {
      throw new Error(
        "No strategies found matching the criteria. Lower minConfidence or minEvidenceStrength."
      );
    }

    console.log(`Found ${strategies.length} strategies to synthesize`);

    // Prepare input for LLM
    const strategiesContext = strategies
      .map(
        (s, idx) => `
Strategy ${idx + 1}: ${s.name}
Type: ${s.strategy_type}
Market: ${s.market}
Timeframe: ${s.timeframe || "Not specified"}
Confidence: ${s.confidence}/10
Evidence: ${s.evidence_strength}
Source: ${s.source?.title || "Unknown"} (${s.source?.publication_year || "Unknown year"})
Source Credibility: ${s.source?.credibility_score || "N/A"}/10
Entry Rules: ${s.entry_rules?.join("; ") || "Not specified"}
Exit Rules: ${s.exit_rules?.join("; ") || "Not specified"}
Indicators: ${s.indicators?.join(", ") || "None"}
Backtest Results: ${s.backtest_results ? JSON.stringify(s.backtest_results) : "No data"}
Limitations: ${s.limitations?.join("; ") || "None mentioned"}
Best Conditions: ${s.best_market_conditions?.join(", ") || "Not specified"}
Worst Conditions: ${s.worst_market_conditions?.join(", ") || "Not specified"}
Description: ${s.description || "No description"}
`
      )
      .join("\n---\n");

    // Get unique sources
    const uniqueSources = new Set(strategies.map((s) => s.source_id));
    const sourcesCount = uniqueSources.size;

    // Synthesize with Gemini
    const result = await generateObject({
      model: google("gemini-2.5-flash"),
      schema: synthesisSchema,
      system: SYNTHESIS_AGENT_PROMPT,
      prompt: `Sintetiza una guía de trading basada en estas ${strategies.length} estrategias de ${sourcesCount} fuentes:

${strategiesContext}

RESTRICCIONES DEL BOT:
- Capital: ~$10,000 USDT
- Par: BTCUSDT
- Timeframe preferido: 1h-1d (intraday a swing)
- Max leverage: 2x
- Opera 24/7 pero no somos HFT

PRIORIDADES:
1. Papers con mejor backtest (Sharpe alto, drawdown bajo)
2. Papers más recientes (post-2020)
3. Papers con mayor credibilidad
4. Evidencia fuerte > evidencia moderada

Genera una guía completa y accionable.`,
    });

    const synthesis = result.object;
    const duration = Date.now() - startTime;
    const tokensUsed =
      (result.usage?.totalTokens || 0);

    // Get latest version number
    const { data: latestGuide } = await supabase
      .from("trading_guides")
      .select("version")
      .order("version", { ascending: false })
      .limit(1)
      .single();

    const newVersion = (latestGuide?.version || 0) + 1;

    // Store in database
    const { data: guideRecord, error: insertError } = await supabase
      .from("trading_guides")
      .insert({
        version: newVersion,
        based_on_sources: sourcesCount,
        based_on_strategies: strategies.length,
        sources_used: Array.from(uniqueSources),
        primary_strategy: synthesis.primary_strategy,
        secondary_strategies: synthesis.secondary_strategies,
        market_conditions_map: synthesis.market_conditions_map,
        avoid_list: synthesis.avoid_list,
        risk_parameters: synthesis.risk_parameters,
        full_guide_markdown: synthesis.full_guide_markdown,
        system_prompt: SYNTHESIS_AGENT_PROMPT,
        executive_summary: synthesis.executive_summary,
        confidence_score: Math.round(synthesis.confidence_score),
        limitations: synthesis.limitations,
        changes_from_previous: latestGuide
          ? `Updated from version ${latestGuide.version}`
          : "Initial version",
      })
      .select("id, version")
      .single();

    if (insertError || !guideRecord) {
      throw new Error(`Failed to insert guide: ${insertError?.message}`);
    }

    console.log(
      `Created trading guide v${guideRecord.version} (ID: ${guideRecord.id})`
    );

    // Log success
    await logAgentAction({
      agent_name: "synthesis",
      action: "synthesize_guide",
      input_summary: `${strategies.length} strategies from ${sourcesCount} sources`,
      output_summary: `Guide v${guideRecord.version}, confidence ${synthesis.confidence_score}/10`,
      reasoning: synthesis.executive_summary,
      tokens_input: undefined,
      tokens_output: undefined,
      tokens_used: tokensUsed,
      duration_ms: duration,
      model_used: "gemini-2.5-flash",
      estimated_cost_usd: calculateCost(tokensUsed),
      status: "success",
    });

    return synthesis;
  } catch (error) {
    const duration = Date.now() - startTime;
    const errorMessage = error instanceof Error ? error.message : String(error);

    // Log error
    await logAgentAction({
      agent_name: "synthesis",
      action: "synthesize_guide",
      input_summary: `minConfidence=${minConfidence}`,
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
