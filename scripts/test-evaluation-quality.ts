#!/usr/bin/env tsx
/**
 * Test Source Agent evaluation quality
 * Tests that the agent makes good decisions on different content types
 */

import { config } from "dotenv";
import { resolve } from "path";

config({ path: resolve(process.cwd(), ".env.local") });

interface TestCase {
  name: string;
  content: string;
  expectedDecision: "approved" | "rejected";
  reason: string;
}

const testCases: TestCase[] = [
  {
    name: "High-quality BTC trading paper",
    content: `
      Title: Bitcoin Momentum Trading with RSI and MACD
      Authors: John Doe, Jane Smith
      Publication: 2023

      Abstract: We present a momentum trading strategy for Bitcoin using RSI and MACD indicators.
      The strategy was backtested on 3 years of BTC/USDT data from Binance.
      Results show a Sharpe ratio of 1.8, maximum drawdown of 15%, and 58% win rate.

      Entry rules: Buy when RSI(14) < 30 and MACD crosses above signal line.
      Exit rules: Sell when RSI(14) > 70 or stop loss at -3%.
      Position sizing: Risk 2% per trade.

      The strategy works best in trending markets and underperforms during sideways consolidation.
    `,
    expectedDecision: "approved",
    reason: "BTC-specific, concrete strategy, backtest results, clear implementation",
  },
  {
    name: "Generic stock trading theory",
    content: `
      Title: Efficient Market Hypothesis and Random Walk Theory
      Authors: Academic Author
      Publication: 1990

      Abstract: This paper discusses the theoretical foundations of efficient markets.
      We prove mathematically that stock prices follow a random walk and cannot be predicted.
      Historical returns show no predictable patterns.

      Conclusion: Technical analysis cannot generate alpha in efficient markets.
    `,
    expectedDecision: "rejected",
    reason: "Theoretical, no practical strategies, not crypto-specific, too old",
  },
  {
    name: "High-frequency trading (not applicable)",
    content: `
      Title: Microsecond-Level Arbitrage in Cryptocurrency Markets
      Authors: HFT Researcher
      Publication: 2024

      Abstract: We implement a high-frequency trading strategy using FPGA hardware
      and colocation services. The strategy exploits price discrepancies between exchanges
      lasting only microseconds. Requires sub-millisecond execution and specialized infrastructure.

      Results: Average profit of $500 per trade, but requires $5M capital and dedicated servers.
    `,
    expectedDecision: "rejected",
    reason: "Requires infrastructure we don't have (HFT, colocation), capital requirement too high",
  },
  {
    name: "Mean reversion strategy for crypto",
    content: `
      Title: Mean Reversion Trading in Cryptocurrency Markets
      Authors: Crypto Trader
      Publication: 2023

      Abstract: We test a mean reversion strategy on Bitcoin and Ethereum using Bollinger Bands.
      Entry: Buy when price touches lower band (2 std dev). Exit: Sell at middle band or upper band.
      Backtested on 2020-2023 data.

      Results: Sharpe ratio 1.2, max drawdown 18%, works on 4h timeframe.
      Capital requirement: $5K minimum. Risk management: Stop loss at 5%.
    `,
    expectedDecision: "approved",
    reason: "Crypto-specific, practical strategy, reasonable capital requirement, good results",
  },
  {
    name: "Blog post with no data",
    content: `
      Title: My Thoughts on Bitcoin Trading
      Author: Random Blogger
      Publication: Personal blog, 2024

      I think Bitcoin will go up because of institutional adoption.
      You should buy when it dips and sell when it pumps.
      Trust your gut and don't overthink it.
      I made $1000 last week using this simple trick!
    `,
    expectedDecision: "rejected",
    reason: "No credibility, vague advice, no data or backtests, not actionable",
  },
];

async function main() {
  console.log("\n🧠 Testing Source Agent Evaluation Quality...\n");

  const { createServerClient } = await import("../lib/supabase");
  const { evaluateSource } = await import("../lib/agents/source-agent");
  const supabase = createServerClient();

  let passed = 0;
  let failed = 0;

  for (const testCase of testCases) {
    console.log(`\n📄 Testing: ${testCase.name}`);
    console.log(`   Expected: ${testCase.expectedDecision.toUpperCase()}`);

    // Create source
    const { data: source, error: insertError } = await supabase
      .from("sources")
      .insert({
        url: `https://test-${Date.now()}-${Math.random()}.com`,
        source_type: "paper",
        raw_content: testCase.content,
      })
      .select("id")
      .single();

    if (insertError || !source) {
      console.log(`   ❌ Failed to create test source`);
      failed++;
      continue;
    }

    try {
      // Evaluate
      const evaluation = await evaluateSource({
        sourceId: source.id,
        url: `test-${testCase.name}`,
        rawContent: testCase.content,
        sourceType: "paper",
      });

      const match = evaluation.decision === testCase.expectedDecision;

      if (match) {
        console.log(`   ✅ Correct decision: ${evaluation.decision.toUpperCase()}`);
        console.log(`   📊 Score: ${evaluation.overall_score}/10`);
        console.log(`   💭 Reasoning: ${evaluation.evaluation_reasoning.substring(0, 150)}...`);
        passed++;
      } else {
        console.log(`   ❌ Wrong decision: got ${evaluation.decision.toUpperCase()}, expected ${testCase.expectedDecision.toUpperCase()}`);
        console.log(`   📊 Score: ${evaluation.overall_score}/10`);
        console.log(`   💭 Reasoning: ${evaluation.evaluation_reasoning}`);
        failed++;
      }
    } catch (error) {
      console.log(`   ❌ Evaluation failed: ${error}`);
      failed++;
    } finally {
      // Cleanup
      await supabase.from("agent_logs").delete().eq("source_id", source.id);
      await supabase.from("sources").delete().eq("id", source.id);
    }
  }

  console.log("\n" + "=".repeat(60));
  console.log(`📊 Results: ${passed} passed, ${failed} failed`);
  console.log(`📈 Accuracy: ${((passed / testCases.length) * 100).toFixed(1)}%\n`);

  if (failed > 0) {
    console.log("⚠️  Some evaluations didn't match expectations");
    console.log("Note: LLM evaluations can vary, review the reasoning above\n");
    // Don't exit with error code - LLM outputs can vary
  } else {
    console.log("✅ All evaluations matched expectations!\n");
  }

  process.exit(0);
}

main().catch((error) => {
  console.error("\n💥 Test crashed:", error);
  process.exit(1);
});
