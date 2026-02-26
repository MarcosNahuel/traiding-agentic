/**
 * Trading Agent - Evaluates strategies and creates trade proposals
 *
 * Supports signal modes via TRADING_SIGNAL_MODE:
 * - llm: LLM-only strategies from DB
 * - deterministic: built-in deterministic v2 strategies
 * - hybrid: deterministic + LLM
 */

import { createServerClient } from "@/lib/supabase";
import { getPrice, getOrderBook, get24hrTicker } from "@/lib/exchanges/binance-client";
import { generateObject } from "ai";
import { google } from "@ai-sdk/google";
import { z } from "zod";
import { TRADING_AGENT_PROMPT } from "@/lib/agents/prompts";
import { isPythonBackendEnabled, getQuantAnalysis } from "@/lib/trading/python-backend";

const GOOGLE_AI_API_KEY = process.env.GOOGLE_AI_API_KEY;

type SignalMode = "llm" | "deterministic" | "hybrid";
const DEFAULT_SIGNAL_MODE: SignalMode = "hybrid";

function getSignalMode(): SignalMode {
  const raw = (process.env.TRADING_SIGNAL_MODE || DEFAULT_SIGNAL_MODE).toLowerCase().trim();
  if (raw === "llm" || raw === "deterministic" || raw === "hybrid") {
    return raw;
  }
  return DEFAULT_SIGNAL_MODE;
}

function getMaxProposalsPerLoop(): number {
  const raw = parseInt(process.env.MAX_PROPOSALS_PER_LOOP || "3", 10);
  if (!Number.isFinite(raw) || raw <= 0) return 3;
  return Math.min(raw, 20);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isUuid(value?: string): boolean {
  if (!value) return false;
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

function toNum(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function safePctDiff(a: number | null, b: number | null): number {
  if (a == null || b == null || b === 0) return 0;
  return ((a - b) / b) * 100;
}

// Zod schema for LLM response - enforces type safety instead of regex parsing
const TradeEvaluationSchema = z.object({
  shouldTrade: z.boolean(),
  type: z.enum(["buy", "sell"]).nullable(),
  confidence: z.number().min(0).max(100),
  reasoning: z.string(),
  suggestedQuantity: z.number().nullable(),
  suggestedPrice: z.number().nullable(),
});

// Exponential backoff retry for LLM calls
async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries = 3,
  baseDelay = 1000
): Promise<T> {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      if (attempt === maxRetries - 1) throw error;
      const delay = baseDelay * Math.pow(2, attempt);
      console.warn(`LLM call failed (attempt ${attempt + 1}/${maxRetries}), retrying in ${delay}ms...`);
      await sleep(delay);
    }
  }
  throw new Error("Unreachable");
}

// ============================================================================
// TYPES
// ============================================================================

export interface MarketConditions {
  symbol: string;
  currentPrice: number;
  priceChange24h: number;
  priceChangePercent24h: number;
  volume24h: number;
  high24h: number;
  low24h: number;
  bidPrice: number;
  askPrice: number;
  spread: number;
  spreadPercent: number;
}

export interface Strategy {
  id: string;
  name: string;
  description: string;
  symbol?: string;
  parameters?: any;
}

export interface TradeSignal {
  strategyId: string;
  strategyName: string;
  type: "buy" | "sell";
  symbol: string;
  confidence: number;
  reasoning: string;
  suggestedQuantity?: number;
  suggestedPrice?: number;
}

interface QuantIndicatorsLike {
  rsi_14?: number;
  adx_14?: number;
  sma_20?: number;
  sma_50?: number;
  sma_200?: number;
  bb_upper?: number;
  bb_middle?: number;
  bb_lower?: number;
  bb_bandwidth?: number;
  atr_14?: number;
  macd_line?: number;
  macd_signal?: number;
  macd_histogram?: number;
  stoch_k?: number;
  stoch_d?: number;
}

interface QuantAnalysisLike {
  is_tradable?: boolean;
  trade_blocks?: string[];
  indicators?: QuantIndicatorsLike;
  entropy?: {
    entropy_ratio?: number;
    is_tradable?: boolean;
  };
  regime?: {
    regime?: string;
    confidence?: number;
    hurst_exponent?: number;
  };
  sr_levels?: {
    levels?: Array<{
      level_type?: string;
      price_level?: number;
      strength?: number;
    }>;
  };
  position_sizing?: {
    recommended_size_usd?: number;
    method?: string;
  };
}

interface SymbolContext {
  marketConditions: MarketConditions;
  quantAnalysis: QuantAnalysisLike | null;
}

const BUILTIN_DETERMINISTIC_STRATEGIES: Strategy[] = [
  {
    id: "trend_momentum_v2",
    name: "Trend Momentum v2",
    description: "ADX + SMA trend confirmation with momentum continuation bias.",
  },
  {
    id: "mean_reversion_v2",
    name: "Mean Reversion v2",
    description: "Range-bound reversion using RSI and Bollinger location.",
  },
  {
    id: "breakout_volatility_v2",
    name: "Breakout Volatility v2",
    description: "Volatility squeeze breakout with trend confirmation.",
  },
];

// ============================================================================
// MARKET DATA FUNCTIONS
// ============================================================================

/**
 * Get current market conditions for a symbol
 */
export async function getMarketConditions(
  symbol: string
): Promise<MarketConditions> {
  const [priceData, ticker, orderBook] = await Promise.all([
    getPrice(symbol),
    get24hrTicker(symbol),
    getOrderBook(symbol, 5),
  ]);

  const currentPrice = parseFloat(priceData.price);
  const bidPrice = parseFloat(orderBook.bids[0][0]);
  const askPrice = parseFloat(orderBook.asks[0][0]);
  const spread = askPrice - bidPrice;
  const spreadPercent = (spread / currentPrice) * 100;

  return {
    symbol,
    currentPrice,
    priceChange24h: parseFloat(ticker.priceChange),
    priceChangePercent24h: parseFloat(ticker.priceChangePercent),
    volume24h: parseFloat(ticker.volume),
    high24h: parseFloat(ticker.highPrice),
    low24h: parseFloat(ticker.lowPrice),
    bidPrice,
    askPrice,
    spread,
    spreadPercent,
  };
}

async function buildSymbolContexts(symbols: string[]): Promise<Record<string, SymbolContext>> {
  const uniqueSymbols = Array.from(new Set(symbols.map((s) => s.toUpperCase())));
  const withQuant = isPythonBackendEnabled();
  const result: Record<string, SymbolContext> = {};

  await Promise.all(
    uniqueSymbols.map(async (symbol) => {
      try {
        const [marketConditions, quantAnalysis] = await Promise.all([
          getMarketConditions(symbol),
          withQuant
            ? (getQuantAnalysis(symbol) as Promise<QuantAnalysisLike>).catch((e) => {
                console.warn(`Failed to fetch quant analysis for ${symbol}:`, e);
                return null;
              })
            : Promise.resolve(null),
        ]);

        result[symbol] = {
          marketConditions,
          quantAnalysis,
        };
      } catch (error) {
        console.error(`Failed to build market context for ${symbol}:`, error);
      }
    })
  );

  return result;
}

// ============================================================================
// STRATEGY EVALUATION
// ============================================================================

function buildQuantSection(quant: QuantAnalysisLike | null): string {
  if (!quant) return "";

  let quantSection = `

QUANT_ANALYSIS (objective data - treat as facts):
- Is Tradable: ${quant.is_tradable} ${quant.trade_blocks?.length ? `(BLOCKED: ${quant.trade_blocks.join(", ")})` : ""}`;

  if (quant.indicators) {
    const ind = quant.indicators;
    quantSection += `
- RSI(14): ${ind.rsi_14?.toFixed(2) ?? "N/A"}
- MACD: line=${ind.macd_line?.toFixed(4) ?? "N/A"}, signal=${ind.macd_signal?.toFixed(4) ?? "N/A"}, hist=${ind.macd_histogram?.toFixed(4) ?? "N/A"}
- ADX(14): ${ind.adx_14?.toFixed(2) ?? "N/A"}
- SMA: 20=${ind.sma_20?.toFixed(2) ?? "N/A"}, 50=${ind.sma_50?.toFixed(2) ?? "N/A"}, 200=${ind.sma_200?.toFixed(2) ?? "N/A"}
- BB: upper=${ind.bb_upper?.toFixed(2) ?? "N/A"}, lower=${ind.bb_lower?.toFixed(2) ?? "N/A"}, bandwidth=${ind.bb_bandwidth?.toFixed(4) ?? "N/A"}
- ATR(14): ${ind.atr_14?.toFixed(2) ?? "N/A"}
- Stochastic: K=${ind.stoch_k?.toFixed(2) ?? "N/A"}, D=${ind.stoch_d?.toFixed(2) ?? "N/A"}`;
  }

  if (quant.entropy) {
    quantSection += `
- Entropy: ratio=${quant.entropy.entropy_ratio?.toFixed(3)}, is_tradable=${quant.entropy.is_tradable}`;
  }

  if (quant.regime) {
    quantSection += `
- Regime: ${quant.regime.regime} (confidence: ${quant.regime.confidence?.toFixed(1)}%, hurst: ${quant.regime.hurst_exponent?.toFixed(3) ?? "N/A"})`;
  }

  if (quant.sr_levels?.levels?.length) {
    const supports = quant.sr_levels.levels.filter((l) => l.level_type === "support").slice(-3);
    const resistances = quant.sr_levels.levels.filter((l) => l.level_type === "resistance").slice(0, 3);
    quantSection += `
- Support levels: ${supports.map((l) => `$${l.price_level?.toFixed(2)} (str:${l.strength})`).join(", ") || "N/A"}
- Resistance levels: ${resistances.map((l) => `$${l.price_level?.toFixed(2)} (str:${l.strength})`).join(", ") || "N/A"}`;
  }

  if (quant.position_sizing) {
    quantSection += `
- Recommended size: $${quant.position_sizing.recommended_size_usd?.toFixed(2)} (method: ${quant.position_sizing.method})`;
  }

  return quantSection;
}

/**
 * Evaluate a strategy against current market conditions using LLM mode.
 */
export async function evaluateStrategy(
  strategy: Strategy,
  marketConditions: MarketConditions,
  quantAnalysis: QuantAnalysisLike | null = null
): Promise<TradeSignal | null> {
  if (!GOOGLE_AI_API_KEY) {
    console.warn("GOOGLE_AI_API_KEY not configured, skipping LLM evaluation");
    return null;
  }

  try {
    const prompt = `${TRADING_AGENT_PROMPT}

STRATEGY:
Name: ${strategy.name}
Description: ${strategy.description}

CURRENT MARKET CONDITIONS (${marketConditions.symbol}):
- Price: $${marketConditions.currentPrice.toLocaleString()}
- 24h Change: ${marketConditions.priceChangePercent24h.toFixed(2)}% (${marketConditions.priceChange24h > 0 ? "+" : ""}$${marketConditions.priceChange24h.toFixed(2)})
- 24h High: $${marketConditions.high24h.toLocaleString()}
- 24h Low: $${marketConditions.low24h.toLocaleString()}
- 24h Volume: ${marketConditions.volume24h.toLocaleString()}
- Bid/Ask Spread: ${marketConditions.spreadPercent.toFixed(3)}%${buildQuantSection(quantAnalysis)}`;

    const { object: result } = await withRetry(() =>
      generateObject({
        model: google("gemini-2.0-flash-exp"),
        schema: TradeEvaluationSchema,
        prompt,
        temperature: 0.3,
      })
    );

    if (!result.shouldTrade || !result.type || result.confidence < 50) {
      return null;
    }

    return {
      strategyId: strategy.id,
      strategyName: strategy.name,
      type: result.type,
      symbol: marketConditions.symbol,
      confidence: result.confidence,
      reasoning: result.reasoning,
      suggestedQuantity: result.suggestedQuantity ?? undefined,
      suggestedPrice: result.suggestedPrice ?? undefined,
    };
  } catch (error) {
    console.error(`Failed to evaluate strategy ${strategy.name}:`, error);
    return null;
  }
}

function normalizeStrategyKey(strategy: Strategy): string {
  const blob = `${strategy.id} ${strategy.name} ${strategy.description}`.toLowerCase();
  if (blob.includes("trend_momentum_v2") || blob.includes("trend momentum v2")) return "trend_momentum_v2";
  if (blob.includes("mean_reversion_v2") || blob.includes("mean reversion v2")) return "mean_reversion_v2";
  if (blob.includes("breakout_volatility_v2") || blob.includes("breakout volatility v2")) return "breakout_volatility_v2";
  return "";
}

function estimateSuggestedQuantity(price: number, quantAnalysis: QuantAnalysisLike | null): number | undefined {
  const sizeUsd = toNum(quantAnalysis?.position_sizing?.recommended_size_usd);
  if (sizeUsd == null || sizeUsd <= 0 || price <= 0) return undefined;
  const qty = sizeUsd / price;
  return Number(Math.max(qty, 0.0001).toFixed(6));
}

function evaluateDeterministicStrategy(
  strategy: Strategy,
  marketConditions: MarketConditions,
  quantAnalysis: QuantAnalysisLike | null
): TradeSignal | null {
  if (!quantAnalysis?.indicators) return null;
  if (quantAnalysis.is_tradable === false) return null;

  const key = normalizeStrategyKey(strategy);
  if (!key) return null;

  const ind = quantAnalysis.indicators;
  const regime = (quantAnalysis.regime?.regime || "").toLowerCase();
  const price = marketConditions.currentPrice;

  const rsi = toNum(ind.rsi_14);
  const adx = toNum(ind.adx_14);
  const sma20 = toNum(ind.sma_20);
  const sma50 = toNum(ind.sma_50);
  const sma200 = toNum(ind.sma_200);
  const bbUpper = toNum(ind.bb_upper);
  const bbLower = toNum(ind.bb_lower);
  const bbBandwidth = toNum(ind.bb_bandwidth);

  const suggestedQuantity = estimateSuggestedQuantity(price, quantAnalysis);

  if (key === "trend_momentum_v2") {
    if (sma20 == null || sma50 == null || rsi == null || adx == null) return null;

    const bullishTrend = sma20 > sma50 && (sma200 == null || sma50 > sma200);
    const bearishTrend = sma20 < sma50 && (sma200 == null || sma50 < sma200);
    const adxStrong = adx >= 22;

    const buy = bullishTrend && adxStrong && rsi >= 48 && rsi <= 72 && (regime === "trending_up" || regime === "volatile");
    const sell = bearishTrend && adxStrong && (rsi <= 45 || regime === "trending_down");

    if (!buy && !sell) return null;

    const trendStrengthPct = Math.min(Math.abs(safePctDiff(sma20, sma50)), 3);
    const confidence = Math.round(
      Math.min(
        92,
        58 +
          (adxStrong ? 12 : 0) +
          trendStrengthPct * 6 +
          (buy && regime === "trending_up" ? 10 : 0) +
          (sell && regime === "trending_down" ? 10 : 0)
      )
    );

    return {
      strategyId: strategy.id,
      strategyName: strategy.name,
      type: buy ? "buy" : "sell",
      symbol: marketConditions.symbol,
      confidence,
      reasoning: `Deterministic trend setup: RSI=${rsi.toFixed(1)}, ADX=${adx.toFixed(1)}, SMA20/SMA50=${sma20.toFixed(2)}/${sma50.toFixed(2)}, regime=${regime || "unknown"}`,
      suggestedQuantity,
    };
  }

  if (key === "mean_reversion_v2") {
    if (rsi == null || adx == null || bbUpper == null || bbLower == null) return null;

    const ranging = adx <= 20 || regime === "ranging";
    const nearLower = price <= bbLower * 1.004;
    const nearUpper = price >= bbUpper * 0.996;

    const buy = ranging && rsi <= 33 && nearLower;
    const sell = ranging && rsi >= 67 && nearUpper;

    if (!buy && !sell) return null;

    const confidence = Math.round(
      Math.min(
        88,
        55 +
          (ranging ? 12 : 0) +
          (buy ? Math.max(0, 35 - rsi) * 0.7 : 0) +
          (sell ? Math.max(0, rsi - 65) * 0.7 : 0)
      )
    );

    return {
      strategyId: strategy.id,
      strategyName: strategy.name,
      type: buy ? "buy" : "sell",
      symbol: marketConditions.symbol,
      confidence,
      reasoning: `Deterministic mean-reversion setup: RSI=${rsi.toFixed(1)}, ADX=${adx.toFixed(1)}, price=${price.toFixed(2)}, BB=[${bbLower.toFixed(2)}, ${bbUpper.toFixed(2)}]`,
      suggestedQuantity,
    };
  }

  if (key === "breakout_volatility_v2") {
    if (adx == null || bbUpper == null || bbLower == null) return null;

    const squeeze = bbBandwidth != null ? bbBandwidth <= 0.03 : false;
    const breakoutUp = price > bbUpper;
    const breakoutDown = price < bbLower;
    const adxValid = adx >= 20;

    const buy = breakoutUp && adxValid && (squeeze || marketConditions.priceChangePercent24h > 1.0);
    const sell = breakoutDown && adxValid && (squeeze || marketConditions.priceChangePercent24h < -1.0);

    if (!buy && !sell) return null;

    const confidence = Math.round(
      Math.min(
        90,
        57 +
          (adxValid ? 10 : 0) +
          (squeeze ? 10 : 0) +
          Math.min(Math.abs(marketConditions.priceChangePercent24h), 5) * 2
      )
    );

    return {
      strategyId: strategy.id,
      strategyName: strategy.name,
      type: buy ? "buy" : "sell",
      symbol: marketConditions.symbol,
      confidence,
      reasoning: `Deterministic breakout setup: ADX=${adx.toFixed(1)}, bandwidth=${bbBandwidth?.toFixed(4) ?? "N/A"}, price=${price.toFixed(2)}, BB=[${bbLower.toFixed(2)}, ${bbUpper.toFixed(2)}]`,
      suggestedQuantity,
    };
  }

  return null;
}

function dedupeSignals(signals: TradeSignal[]): TradeSignal[] {
  const byKey = new Map<string, TradeSignal>();

  for (const signal of signals) {
    const key = `${signal.symbol}:${signal.type}`;
    const existing = byKey.get(key);
    if (!existing || signal.confidence > existing.confidence) {
      byKey.set(key, signal);
    }
  }

  return Array.from(byKey.values()).sort((a, b) => b.confidence - a.confidence);
}

async function loadValidatedStrategies(limit = 10): Promise<Strategy[]> {
  const supabase = createServerClient();

  const { data, error } = await supabase
    .from("strategies_found")
    .select("*")
    .in("validation_status", ["validated", "approved"])
    .limit(limit);

  if (error) {
    console.error("Failed to load validated strategies:", error);
    return [];
  }

  return (data || []).map((s: any) => ({
    id: String(s.id),
    name: String(s.name || "Unnamed Strategy"),
    description: String(s.description || ""),
    symbol: typeof s.symbol === "string" ? s.symbol : undefined,
    parameters: s.parameters,
  }));
}

/**
 * Evaluate active strategies according to TRADING_SIGNAL_MODE.
 */
export async function evaluateAllStrategies(
  symbols: string[] = ["BTCUSDT", "ETHUSDT"]
): Promise<TradeSignal[]> {
  const signalMode = getSignalMode();
  const normalizedSymbols = Array.from(new Set(symbols.map((s) => s.toUpperCase())));

  console.log(`Evaluating strategies (mode=${signalMode}, symbols=${normalizedSymbols.join(",")})`);

  const contexts = await buildSymbolContexts(normalizedSymbols);
  const availableSymbols = Object.keys(contexts);
  if (availableSymbols.length === 0) {
    console.log("No symbol contexts available, skipping strategy evaluation");
    return [];
  }

  const signals: TradeSignal[] = [];

  if (signalMode === "deterministic" || signalMode === "hybrid") {
    for (const strategy of BUILTIN_DETERMINISTIC_STRATEGIES) {
      for (const symbol of availableSymbols) {
        const ctx = contexts[symbol];
        const signal = evaluateDeterministicStrategy(strategy, ctx.marketConditions, ctx.quantAnalysis);
        if (signal) {
          signals.push(signal);
          console.log(`Signal generated (deterministic): ${signal.type.toUpperCase()} ${signal.symbol} (${signal.confidence}%)`);
        }
      }
    }
  }

  if (signalMode === "llm" || signalMode === "hybrid") {
    const llmStrategies = await loadValidatedStrategies(10);
    if (llmStrategies.length === 0) {
      console.log("No validated strategies found for LLM evaluation");
    } else {
      const extraSymbols = Array.from(
        new Set(
          llmStrategies
            .map((s) => (s.symbol ? s.symbol.toUpperCase() : null))
            .filter((s): s is string => !!s && !contexts[s])
        )
      );

      if (extraSymbols.length > 0) {
        const extraContexts = await buildSymbolContexts(extraSymbols);
        Object.assign(contexts, extraContexts);
      }

      const llmSymbolsUniverse = Object.keys(contexts);

      for (const strategy of llmStrategies) {
        const symbolsToCheck = strategy.symbol ? [strategy.symbol.toUpperCase()] : llmSymbolsUniverse;

        for (const symbol of symbolsToCheck) {
          const ctx = contexts[symbol];
          if (!ctx) continue;

          try {
            const signal = await evaluateStrategy(strategy, ctx.marketConditions, ctx.quantAnalysis);
            if (signal) {
              signals.push(signal);
              console.log(`Signal generated (llm): ${signal.type.toUpperCase()} ${signal.symbol} (${signal.confidence}%)`);
            }
          } catch (error) {
            console.error(`Failed to evaluate ${strategy.name} for ${symbol}:`, error);
          }

          await sleep(350);
        }
      }
    }
  }

  return dedupeSignals(signals);
}

// ============================================================================
// TRADE PROPOSAL CREATION
// ============================================================================

/**
 * Create a trade proposal from a signal
 */
export async function createProposalFromSignal(
  signal: TradeSignal
): Promise<string | null> {
  try {
    // Get current price if not suggested
    let price = signal.suggestedPrice;
    if (!price) {
      const priceData = await getPrice(signal.symbol);
      price = parseFloat(priceData.price);
    }

    // Determine quantity
    let quantity = signal.suggestedQuantity || 0.001;

    // For sells, check if we have an open position
    if (signal.type === "sell") {
      const supabase = createServerClient();
      const { data: position } = await supabase
        .from("positions")
        .select("current_quantity")
        .eq("symbol", signal.symbol)
        .eq("status", "open")
        .order("opened_at", { ascending: false })
        .limit(1)
        .single();

      if (position) {
        quantity = parseFloat(position.current_quantity);
      } else {
        console.log(`No open position found for ${signal.symbol}, skipping sell signal`);
        return null;
      }
    }

    const strategyId = isUuid(signal.strategyId) ? signal.strategyId : undefined;

    // Create proposal via API
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_APP_URL || (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000")}/api/trades/proposals`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: signal.type,
          symbol: signal.symbol,
          quantity,
          price: signal.suggestedPrice || undefined,
          orderType: signal.suggestedPrice ? "LIMIT" : "MARKET",
          strategyId,
          reasoning: `${signal.strategyName}: ${signal.reasoning} (Confidence: ${signal.confidence}%)`,
        }),
      }
    );

    if (!response.ok) {
      const error = await response.text();
      console.error("Failed to create proposal:", error);
      return null;
    }

    const result = await response.json();
    console.log(`Proposal created: ${result.proposalId}`);

    return result.proposalId;
  } catch (error) {
    console.error("Failed to create proposal from signal:", error);
    return null;
  }
}

/**
 * Main trading loop - evaluate strategies and create proposals
 */
export async function runTradingLoop(): Promise<{
  signalsGenerated: number;
  proposalsCreated: number;
  signals: TradeSignal[];
}> {
  console.log("Running trading loop...");

  try {
    const allSignals = dedupeSignals(await evaluateAllStrategies());

    if (allSignals.length === 0) {
      console.log("No trading signals generated");
      return { signalsGenerated: 0, proposalsCreated: 0, signals: [] };
    }

    const maxProposals = getMaxProposalsPerLoop();
    const signalsToExecute = allSignals.slice(0, maxProposals);

    if (allSignals.length > maxProposals) {
      console.log(`Capping proposals to top ${maxProposals} signals by confidence (${allSignals.length} generated)`);
    }

    let proposalsCreated = 0;
    for (const signal of signalsToExecute) {
      const proposalId = await createProposalFromSignal(signal);
      if (proposalId) {
        proposalsCreated++;
      }
      await sleep(200);
    }

    console.log(`Trading loop complete: ${proposalsCreated} proposals created (${allSignals.length} signals generated)`);

    return {
      signalsGenerated: allSignals.length,
      proposalsCreated,
      signals: allSignals,
    };
  } catch (error) {
    console.error("Trading loop error:", error);
    return { signalsGenerated: 0, proposalsCreated: 0, signals: [] };
  }
}
