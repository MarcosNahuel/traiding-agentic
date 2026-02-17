/**
 * Trading Agent - Evaluates strategies and creates trade proposals
 *
 * This agent:
 * 1. Monitors market conditions
 * 2. Evaluates active strategies
 * 3. Creates trade proposals when conditions are met
 * 4. Does NOT execute trades (that's the executor's job)
 */

import { createServerClient } from "@/lib/supabase";
import { getPrice, getOrderBook, get24hrTicker } from "@/lib/exchanges/binance-client";
import { generateObject } from "ai";
import { google } from "@ai-sdk/google";
import { z } from "zod";
import { TRADING_AGENT_PROMPT } from "@/lib/agents/prompts";

const GOOGLE_AI_API_KEY = process.env.GOOGLE_AI_API_KEY;

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
      await new Promise((resolve) => setTimeout(resolve, delay));
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
  symbol?: string; // If strategy is symbol-specific
  parameters?: any;
}

export interface TradeSignal {
  strategyId: string;
  strategyName: string;
  type: "buy" | "sell";
  symbol: string;
  confidence: number; // 0-100
  reasoning: string;
  suggestedQuantity?: number;
  suggestedPrice?: number;
}

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

// ============================================================================
// STRATEGY EVALUATION
// ============================================================================

/**
 * Evaluate a strategy against current market conditions
 */
export async function evaluateStrategy(
  strategy: Strategy,
  marketConditions: MarketConditions
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
- Bid/Ask Spread: ${marketConditions.spreadPercent.toFixed(3)}%`;

    const { object: result } = await withRetry(() =>
      generateObject({
        model: google("gemini-2.0-flash-exp"),
        schema: TradeEvaluationSchema,
        prompt,
        temperature: 0.3,
      })
    );

    // Validate response
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
    console.error("Failed to evaluate strategy:", error);
    return null;
  }
}

/**
 * Evaluate all active strategies
 */
export async function evaluateAllStrategies(
  symbols: string[] = ["BTCUSDT", "ETHUSDT"]
): Promise<TradeSignal[]> {
  const supabase = createServerClient();

  // Get all approved strategies
  const { data: strategies } = await supabase
    .from("strategies_found")
    .select("*")
    .eq("validation_status", "approved")
    .limit(10); // Limit to avoid rate limits

  if (!strategies || strategies.length === 0) {
    console.log("No approved strategies found");
    return [];
  }

  console.log(`Evaluating ${strategies.length} strategies...`);

  const signals: TradeSignal[] = [];

  for (const strategy of strategies) {
    // Determine which symbols to check
    const symbolsToCheck = strategy.symbol
      ? [strategy.symbol]
      : symbols;

    for (const symbol of symbolsToCheck) {
      try {
        // Get market conditions
        const conditions = await getMarketConditions(symbol);

        // Evaluate strategy
        const signal = await evaluateStrategy(
          {
            id: strategy.id,
            name: strategy.name,
            description: strategy.description,
            symbol: strategy.symbol,
            parameters: strategy.parameters,
          },
          conditions
        );

        if (signal) {
          signals.push(signal);
          console.log(
            `✅ Signal generated: ${signal.type.toUpperCase()} ${signal.symbol} (confidence: ${signal.confidence}%)`
          );
        }

        // Small delay to avoid rate limiting
        await new Promise((resolve) => setTimeout(resolve, 500));
      } catch (error) {
        console.error(
          `Failed to evaluate ${strategy.name} for ${symbol}:`,
          error
        );
      }
    }
  }

  return signals;
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
    let quantity = signal.suggestedQuantity || 0.001; // Default 0.001 BTC

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

    const notional = quantity * price;

    // Create proposal via API
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000"}/api/trades/proposals`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: signal.type,
          symbol: signal.symbol,
          quantity,
          price: signal.suggestedPrice || undefined,
          orderType: signal.suggestedPrice ? "LIMIT" : "MARKET",
          strategyId: signal.strategyId,
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
    console.log(`✅ Proposal created: ${result.proposalId}`);

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
  console.log("🤖 Running trading loop...");

  try {
    // Evaluate all strategies
    const signals = await evaluateAllStrategies();

    if (signals.length === 0) {
      console.log("No trading signals generated");
      return { signalsGenerated: 0, proposalsCreated: 0, signals: [] };
    }

    console.log(`Generated ${signals.length} trading signals`);

    // Create proposals from signals
    let proposalsCreated = 0;
    for (const signal of signals) {
      const proposalId = await createProposalFromSignal(signal);
      if (proposalId) {
        proposalsCreated++;
      }

      // Small delay between proposals
      await new Promise((resolve) => setTimeout(resolve, 200));
    }

    console.log(`✅ Trading loop complete: ${proposalsCreated} proposals created`);

    return {
      signalsGenerated: signals.length,
      proposalsCreated,
      signals,
    };
  } catch (error) {
    console.error("Trading loop error:", error);
    return { signalsGenerated: 0, proposalsCreated: 0, signals: [] };
  }
}
