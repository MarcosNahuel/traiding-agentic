#!/usr/bin/env tsx
/**
 * Test Reader Agent - Extract strategies from approved papers
 */

import { config } from "dotenv";
import { resolve } from "path";

config({ path: resolve(process.cwd(), ".env.local") });

const testPaper = `
Title: Bitcoin Momentum Trading with RSI and MACD
Authors: John Doe, Jane Smith
Publication: 2023
Journal: Journal of Cryptocurrency Trading Research

Abstract:
We present a momentum trading strategy for Bitcoin using RSI and MACD indicators.
The strategy was backtested on 3 years of BTC/USDT data from Binance (2020-2023).

Methodology:
Our strategy combines two classic technical indicators:
1. RSI (Relative Strength Index) with a 14-period setting
2. MACD (Moving Average Convergence Divergence) with standard parameters (12, 26, 9)

Entry Rules:
- Buy when RSI(14) < 30 (oversold condition)
- AND MACD line crosses above signal line
- Position enters at market price on next candle

Exit Rules:
- Sell when RSI(14) > 70 (overbought condition)
- OR stop loss triggered at -3% from entry
- OR MACD line crosses below signal line

Position Sizing:
We risk 2% of capital per trade, using the stop loss distance to calculate position size.
Maximum position size is 20% of portfolio.

Backtest Results:
Over the 3-year period (2020-2023):
- Sharpe Ratio: 1.8
- Maximum Drawdown: 15%
- Win Rate: 58%
- Total Trades: 247
- Average Trade Duration: 4.2 days
- Best Month: +12.4% (Nov 2020)
- Worst Month: -8.2% (May 2021)

The strategy works best during trending markets with clear momentum.
It underperforms during sideways consolidation when price oscillates without clear direction.

Risk Warnings:
1. The strategy can generate false signals in ranging markets
2. Transaction costs were not included in backtest (assumes 0.1% fee would reduce returns by ~1.5% annually)
3. Requires disciplined execution - emotional trading will hurt results
4. Past performance does not guarantee future results
5. Crypto markets are highly volatile and can change regime quickly

Comparison with Prior Research:
Our results confirm the findings of Martinez et al. (2022) who found RSI-based strategies
effective in crypto markets. However, our Sharpe ratio is lower than the 2.1 reported by
Chen (2021), possibly due to our more conservative stop-loss approach.

Limitations:
- Backtest period includes the 2020-2021 bull market which may inflate results
- Strategy not tested on bear market conditions
- Assumes instant execution which may not be realistic during high volatility
- Does not account for slippage

Best Market Conditions:
- Trending markets with momentum
- Medium to high volatility
- Clear support/resistance levels

Worst Market Conditions:
- Sideways consolidation
- Low volatility ranges
- High-frequency oscillations

Conclusion:
The RSI-MACD momentum strategy shows promise for Bitcoin trading but requires
careful risk management and awareness of market regime.
`;

async function main() {
  console.log("\n🔍 Testing Reader Agent...\n");

  const { createServerClient } = await import("../lib/supabase");
  const { extractPaper } = await import("../lib/agents/reader-agent");
  const supabase = createServerClient();

  // Cleanup existing test data
  console.log("🧹 Cleaning up previous test data...");
  const { data: existingSources } = await supabase
    .from("sources")
    .select("id")
    .eq("url", "https://test-reader-agent.com");

  if (existingSources && existingSources.length > 0) {
    for (const src of existingSources) {
      await supabase.from("strategies_found").delete().eq("source_id", src.id);
      await supabase
        .from("paper_extractions")
        .delete()
        .eq("source_id", src.id);
      await supabase.from("agent_logs").delete().eq("source_id", src.id);
      await supabase.from("sources").delete().eq("id", src.id);
    }
    console.log(`   Deleted ${existingSources.length} previous test sources\n`);
  }

  // Create approved source with content
  console.log("📄 Creating test source...");
  const { data: source, error: insertError } = await supabase
    .from("sources")
    .insert({
      url: "https://test-reader-agent.com",
      source_type: "paper",
      status: "approved",
      title: "Bitcoin Momentum Trading with RSI and MACD",
      raw_content: testPaper,
      content_length: testPaper.length,
      fetched_at: new Date().toISOString(),
      relevance_score: 8.0,
      credibility_score: 7.0,
      applicability_score: 7.5,
      overall_score: 7.6,
      tags: ["btc", "momentum", "rsi", "macd"],
      summary: "Momentum strategy using RSI and MACD on Bitcoin",
    })
    .select("id")
    .single();

  if (insertError || !source) {
    console.error("❌ Failed to create test source:", insertError);
    process.exit(1);
  }

  console.log(`   Created source: ${source.id}\n`);

  try {
    // Extract strategies
    console.log("🧠 Extracting strategies with Reader Agent...");
    const startTime = Date.now();

    const extraction = await extractPaper({
      sourceId: source.id,
      title: "Bitcoin Momentum Trading with RSI and MACD",
      rawContent: testPaper,
    });

    const duration = Date.now() - startTime;

    console.log("\n✅ Extraction completed!\n");
    console.log("=" .repeat(60));
    console.log(`⏱️  Duration: ${(duration / 1000).toFixed(1)}s`);
    console.log(`📊 Confidence Score: ${extraction.confidence_score}/10`);
    console.log(`\n📝 Executive Summary:`);
    console.log(`   ${extraction.executive_summary}\n`);

    console.log(`🎯 Strategies Found: ${extraction.strategies.length}`);
    extraction.strategies.forEach((strategy, idx) => {
      console.log(`\n   ${idx + 1}. ${strategy.name}`);
      console.log(`      Type: ${strategy.strategy_type}`);
      console.log(`      Timeframe: ${strategy.timeframe || "Not specified"}`);
      console.log(`      Indicators: ${strategy.indicators.join(", ")}`);
      console.log(`      Entry Rules: ${strategy.entry_rules.length} rules`);
      console.log(`      Exit Rules: ${strategy.exit_rules.length} rules`);
      console.log(`      Confidence: ${strategy.confidence}/10`);
      console.log(`      Evidence: ${strategy.evidence_strength}`);

      if (strategy.backtest_results) {
        console.log(`      Backtest Results:`);
        if (strategy.backtest_results.sharpe_ratio) {
          console.log(
            `         - Sharpe: ${strategy.backtest_results.sharpe_ratio}`
          );
        }
        if (strategy.backtest_results.max_drawdown) {
          console.log(
            `         - Max DD: ${strategy.backtest_results.max_drawdown}%`
          );
        }
        if (strategy.backtest_results.win_rate) {
          console.log(
            `         - Win Rate: ${strategy.backtest_results.win_rate}%`
          );
        }
      }

      console.log(`      Limitations: ${strategy.limitations.length} noted`);
    });

    console.log(`\n💡 Key Insights: ${extraction.key_insights.length}`);
    extraction.key_insights.forEach((insight, idx) => {
      console.log(`   ${idx + 1}. ${insight}`);
    });

    console.log(`\n⚠️  Risk Warnings: ${extraction.risk_warnings.length}`);
    extraction.risk_warnings.forEach((warning, idx) => {
      console.log(`   ${idx + 1}. ${warning}`);
    });

    // Verify database records
    console.log("\n🗄️  Verifying database records...\n");

    const { data: extractionRecord } = await supabase
      .from("paper_extractions")
      .select("*")
      .eq("source_id", source.id)
      .single();

    if (!extractionRecord) {
      console.log("   ❌ Extraction record not found in database");
    } else {
      console.log(`   ✅ Extraction record created (ID: ${extractionRecord.id})`);
      console.log(`      Strategies: ${extractionRecord.strategies?.length || 0}`);
      console.log(`      Key Insights: ${extractionRecord.key_insights?.length || 0}`);
      console.log(`      Risk Warnings: ${extractionRecord.risk_warnings?.length || 0}`);
    }

    const { data: strategies } = await supabase
      .from("strategies_found")
      .select("*")
      .eq("source_id", source.id);

    console.log(`   ✅ Strategy records: ${strategies?.length || 0}`);
    strategies?.forEach((strat) => {
      console.log(`      - ${strat.name} (${strat.strategy_type})`);
    });

    const { data: logs } = await supabase
      .from("agent_logs")
      .select("*")
      .eq("source_id", source.id)
      .eq("agent_name", "reader");

    console.log(`   ✅ Agent logs: ${logs?.length || 0}`);
    logs?.forEach((log) => {
      console.log(`      - ${log.action}: ${log.status} (${log.duration_ms}ms)`);
      if (log.tokens_used) {
        console.log(`        Tokens: ${log.tokens_used}, Cost: $${log.estimated_cost_usd?.toFixed(6) || "0"}`);
      }
    });

    // Check source status
    const { data: updatedSource } = await supabase
      .from("sources")
      .select("status")
      .eq("id", source.id)
      .single();

    console.log(`   ✅ Source status: ${updatedSource?.status}`);

    console.log("\n" + "=".repeat(60));
    console.log("✅ Reader Agent test completed successfully!\n");

    // Cleanup
    console.log("🧹 Cleaning up test data...");
    await supabase.from("strategies_found").delete().eq("source_id", source.id);
    await supabase
      .from("paper_extractions")
      .delete()
      .eq("source_id", source.id);
    await supabase.from("agent_logs").delete().eq("source_id", source.id);
    await supabase.from("sources").delete().eq("id", source.id);
    console.log("   Done!\n");

    process.exit(0);
  } catch (error) {
    console.error("\n💥 Test failed:", error);

    // Cleanup on error
    await supabase.from("strategies_found").delete().eq("source_id", source.id);
    await supabase
      .from("paper_extractions")
      .delete()
      .eq("source_id", source.id);
    await supabase.from("agent_logs").delete().eq("source_id", source.id);
    await supabase.from("sources").delete().eq("id", source.id);

    process.exit(1);
  }
}

main().catch((error) => {
  console.error("\n💥 Test crashed:", error);
  process.exit(1);
});
