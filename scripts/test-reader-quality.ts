#!/usr/bin/env tsx
/**
 * Test Reader Agent extraction quality
 * Tests that the agent extracts strategies correctly from different paper types
 */

import { config } from "dotenv";
import { resolve } from "path";

config({ path: resolve(process.cwd(), ".env.local") });

interface TestCase {
  name: string;
  content: string;
  expectedStrategies: number;
  expectedInsights: number;
  expectedWarnings: number;
  minConfidence: number;
}

const testCases: TestCase[] = [
  {
    name: "Complete paper with strategy details",
    content: `
      Title: RSI Mean Reversion in BTC

      Strategy: Buy when RSI(14) < 30, sell when RSI(14) > 70.
      Stop loss at -5%. Position size: 10% of capital.

      Backtest: 2020-2023 BTC/USDT
      - Sharpe Ratio: 1.5
      - Max Drawdown: 12%
      - Win Rate: 62%

      Works best in ranging markets. Fails in strong trends.

      Risk: Can give false signals during volatility spikes.
    `,
    expectedStrategies: 1,
    expectedInsights: 0,
    expectedWarnings: 1,
    minConfidence: 7,
  },
  {
    name: "Paper with multiple strategies",
    content: `
      Title: Three Momentum Strategies for Bitcoin

      Strategy 1: MACD Crossover
      - Buy when MACD crosses above signal
      - Sell when MACD crosses below signal
      - Sharpe: 1.2, Max DD: 18%

      Strategy 2: Bollinger Band Breakout
      - Buy when price breaks above upper band
      - Sell when price returns to middle band
      - Sharpe: 1.8, Max DD: 10%

      Strategy 3: Volume + Price Action
      - Buy on high volume breakouts above resistance
      - Sell on low volume rejection at resistance
      - Sharpe: 2.1, Max DD: 8%

      All strategies tested on BTC 2019-2023.
    `,
    expectedStrategies: 3,
    expectedInsights: 0,
    expectedWarnings: 0,
    minConfidence: 6,
  },
  {
    name: "Paper with insights but vague strategy",
    content: `
      Title: Market Microstructure in Crypto

      We found that order book imbalance predicts short-term price movements.
      When buy orders exceed sell orders by >30%, price tends to rise in next 5 minutes.

      Also, funding rates above 0.1% indicate overheated longs and potential reversal.

      Recommendation: Use order book data to time entries and exits.
      However, specific implementation depends on exchange APIs and latency.
    `,
    expectedStrategies: 0,
    expectedInsights: 2,
    expectedWarnings: 0,
    minConfidence: 5,
  },
  {
    name: "Paper with risk warnings",
    content: `
      Title: High Leverage Trading Risks

      Strategy: 10x leveraged breakout trading on BTC.

      Results: High returns in bull markets but catastrophic losses in volatility.

      Warnings:
      - Liquidation risk is extreme with 10x leverage
      - Funding costs eat into profits
      - Black swan events can wipe out account
      - Not suitable for retail traders
      - Requires 24/7 monitoring
    `,
    expectedStrategies: 1,
    expectedInsights: 0,
    expectedWarnings: 5,
    minConfidence: 4,
  },
  {
    name: "Theoretical paper with no concrete strategies",
    content: `
      Title: Efficient Market Hypothesis in Crypto

      We prove mathematically that crypto markets exhibit semi-strong efficiency.
      Technical analysis cannot generate alpha in the long run.

      Our model shows that information is quickly priced in.

      This contradicts claims by momentum traders.
    `,
    expectedStrategies: 0,
    expectedInsights: 1,
    expectedWarnings: 0,
    minConfidence: 3,
  },
];

async function main() {
  console.log("\n🧠 Testing Reader Agent Extraction Quality...\n");

  const { createServerClient } = await import("../lib/supabase");
  const { extractPaper } = await import("../lib/agents/reader-agent");
  const supabase = createServerClient();

  let passed = 0;
  let failed = 0;

  for (const testCase of testCases) {
    console.log(`\n📄 Testing: ${testCase.name}`);
    console.log(
      `   Expected: ${testCase.expectedStrategies} strategies, ${testCase.expectedInsights} insights, ${testCase.expectedWarnings} warnings`
    );

    // Create source
    const { data: source, error: insertError } = await supabase
      .from("sources")
      .insert({
        url: `https://test-${Date.now()}-${Math.random()}.com`,
        source_type: "paper",
        status: "approved",
        title: testCase.name,
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
      // Extract
      const extraction = await extractPaper({
        sourceId: source.id,
        title: testCase.name,
        rawContent: testCase.content,
      });

      // Verify extraction
      const strategiesMatch =
        extraction.strategies.length === testCase.expectedStrategies;
      const insightsMatch =
        extraction.key_insights.length >= testCase.expectedInsights;
      const warningsMatch =
        extraction.risk_warnings.length >= testCase.expectedWarnings;
      const confidenceOk =
        extraction.confidence_score >= testCase.minConfidence;

      const allMatch =
        strategiesMatch && insightsMatch && warningsMatch && confidenceOk;

      if (allMatch) {
        console.log(`   ✅ Extraction quality verified`);
        console.log(
          `      Strategies: ${extraction.strategies.length}/${testCase.expectedStrategies}`
        );
        console.log(
          `      Insights: ${extraction.key_insights.length}/${testCase.expectedInsights}`
        );
        console.log(
          `      Warnings: ${extraction.risk_warnings.length}/${testCase.expectedWarnings}`
        );
        console.log(
          `      Confidence: ${extraction.confidence_score}/10 (min: ${testCase.minConfidence})`
        );
        passed++;
      } else {
        console.log(`   ❌ Extraction quality issues:`);
        if (!strategiesMatch) {
          console.log(
            `      Strategies: got ${extraction.strategies.length}, expected ${testCase.expectedStrategies}`
          );
        }
        if (!insightsMatch) {
          console.log(
            `      Insights: got ${extraction.key_insights.length}, expected >=${testCase.expectedInsights}`
          );
        }
        if (!warningsMatch) {
          console.log(
            `      Warnings: got ${extraction.risk_warnings.length}, expected >=${testCase.expectedWarnings}`
          );
        }
        if (!confidenceOk) {
          console.log(
            `      Confidence: got ${extraction.confidence_score}, expected >=${testCase.minConfidence}`
          );
        }
        failed++;
      }
    } catch (error) {
      console.log(`   ❌ Extraction failed: ${error}`);
      failed++;
    } finally {
      // Cleanup
      await supabase.from("strategies_found").delete().eq("source_id", source.id);
      await supabase
        .from("paper_extractions")
        .delete()
        .eq("source_id", source.id);
      await supabase.from("agent_logs").delete().eq("source_id", source.id);
      await supabase.from("sources").delete().eq("id", source.id);
    }
  }

  console.log("\n" + "=".repeat(60));
  console.log(`📊 Results: ${passed} passed, ${failed} failed`);
  console.log(
    `📈 Accuracy: ${((passed / testCases.length) * 100).toFixed(1)}%\n`
  );

  if (failed > 0) {
    console.log("⚠️  Some extractions didn't match expectations");
    console.log("Note: LLM extractions can vary, review the output above\n");
    // Don't exit with error code - LLM outputs can vary
  } else {
    console.log("✅ All extractions matched expectations!\n");
  }

  process.exit(0);
}

main().catch((error) => {
  console.error("\n💥 Test crashed:", error);
  process.exit(1);
});
