#!/usr/bin/env tsx
/**
 * Test Synthesis Agent - Generate trading guide from multiple strategies
 */

import { config } from "dotenv";
import { resolve } from "path";

config({ path: resolve(process.cwd(), ".env.local") });

// Test data: Mock strategies from different papers
const mockSources = [
  {
    url: "https://test-synthesis-1.com",
    source_type: "paper" as const,
    title: "RSI Mean Reversion in BTC Markets",
    authors: "John Doe",
    publication_year: 2023,
    overall_score: 8.5,
    credibility_score: 9.0,
    status: "processed" as const,
  },
  {
    url: "https://test-synthesis-2.com",
    source_type: "paper" as const,
    title: "MACD Momentum Trading for Crypto",
    authors: "Jane Smith",
    publication_year: 2024,
    overall_score: 7.8,
    credibility_score: 8.0,
    status: "processed" as const,
  },
  {
    url: "https://test-synthesis-3.com",
    source_type: "paper" as const,
    title: "Bollinger Bands Breakout Strategy",
    authors: "Mike Johnson",
    publication_year: 2023,
    overall_score: 8.0,
    credibility_score: 7.5,
    status: "processed" as const,
  },
];

const mockStrategies = [
  {
    name: "RSI Mean Reversion",
    description: "Buy oversold, sell overbought using RSI indicator",
    strategy_type: "mean_reversion" as const,
    market: "btc",
    timeframe: "4h",
    indicators: ["RSI(14)"],
    entry_rules: ["RSI < 30", "Price at support"],
    exit_rules: ["RSI > 70", "Stop loss at -3%"],
    position_sizing: "Risk 2% per trade",
    backtest_results: {
      sharpe_ratio: 1.8,
      max_drawdown: 12,
      win_rate: 65,
      period: "2020-2023",
    },
    limitations: ["Fails in strong trends", "Requires ranging market"],
    best_market_conditions: ["Ranging", "Low volatility"],
    worst_market_conditions: ["Strong trends", "High volatility"],
    confidence: 9,
    evidence_strength: "strong" as const,
  },
  {
    name: "MACD Momentum",
    description: "Trend-following using MACD crossovers",
    strategy_type: "momentum" as const,
    market: "btc",
    timeframe: "1d",
    indicators: ["MACD(12,26,9)"],
    entry_rules: ["MACD crosses above signal", "Price above 50 EMA"],
    exit_rules: ["MACD crosses below signal", "Stop at -5%"],
    position_sizing: "1.5% risk per trade",
    backtest_results: {
      sharpe_ratio: 2.1,
      max_drawdown: 18,
      win_rate: 58,
      period: "2021-2024",
    },
    limitations: ["Lags in fast markets", "False signals in ranging"],
    best_market_conditions: ["Trending", "Medium volatility"],
    worst_market_conditions: ["Choppy", "Ranging"],
    confidence: 8,
    evidence_strength: "strong" as const,
  },
  {
    name: "Bollinger Breakout",
    description: "Breakout strategy using Bollinger Bands",
    strategy_type: "breakout" as const,
    market: "btc",
    timeframe: "1h",
    indicators: ["Bollinger Bands(20,2)"],
    entry_rules: ["Price breaks above upper band", "Volume surge"],
    exit_rules: ["Price returns to middle band", "Stop at -2%"],
    position_sizing: "Risk 1% per trade",
    backtest_results: {
      sharpe_ratio: 1.5,
      max_drawdown: 10,
      win_rate: 52,
      period: "2022-2023",
    },
    limitations: ["Many false breakouts", "High trade frequency"],
    best_market_conditions: ["High volatility", "Breakout phase"],
    worst_market_conditions: ["Low volatility", "Ranging"],
    confidence: 7,
    evidence_strength: "moderate" as const,
  },
];

async function main() {
  console.log("\n🔬 Testing Synthesis Agent...\n");

  const { createServerClient } = await import("../lib/supabase");
  const { synthesizeGuide } = await import("../lib/agents/synthesis-agent");
  const supabase = createServerClient();

  // Cleanup previous test data
  console.log("🧹 Cleaning up previous test data...");
  const { data: existingSources } = await supabase
    .from("sources")
    .select("id")
    .like("url", "https://test-synthesis-%");

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

  // Delete test guides
  const { data: existingGuides } = await supabase
    .from("trading_guides")
    .select("version")
    .order("version", { ascending: false });

  if (existingGuides && existingGuides.length > 0) {
    await supabase.from("trading_guides").delete().neq("version", 0); // Delete all
    console.log(`   Deleted ${existingGuides.length} previous test guides\n`);
  }

  console.log("📄 Creating test sources and strategies...\n");

  const createdSourceIds: string[] = [];

  // Create sources and strategies
  for (let i = 0; i < mockSources.length; i++) {
    const mockSource = mockSources[i];
    const mockStrategy = mockStrategies[i];

    // Create source
    const { data: source, error: sourceError } = await supabase
      .from("sources")
      .insert(mockSource)
      .select("id")
      .single();

    if (sourceError || !source) {
      console.error(`   ❌ Failed to create source ${i + 1}:`, sourceError);
      continue;
    }

    createdSourceIds.push(source.id);
    console.log(`   ✅ Created source ${i + 1}: ${mockSource.title}`);

    // Create extraction
    const { data: extraction, error: extractionError } = await supabase
      .from("paper_extractions")
      .insert({
        source_id: source.id,
        strategies: [mockStrategy],
        key_insights: [],
        risk_warnings: [],
        executive_summary: `Summary of ${mockSource.title}`,
        confidence_score: mockStrategy.confidence,
      })
      .select("id")
      .single();

    if (extractionError || !extraction) {
      console.error(
        `   ❌ Failed to create extraction ${i + 1}:`,
        extractionError
      );
      continue;
    }

    // Create strategy
    const { error: strategyError } = await supabase
      .from("strategies_found")
      .insert({
        source_id: source.id,
        extraction_id: extraction.id,
        ...mockStrategy,
      });

    if (strategyError) {
      console.error(
        `   ❌ Failed to create strategy ${i + 1}:`,
        strategyError
      );
    } else {
      console.log(`   ✅ Created strategy: ${mockStrategy.name}`);
    }
  }

  console.log("\n🧠 Synthesizing trading guide...\n");

  try {
    const startTime = Date.now();

    const synthesis = await synthesizeGuide({
      minConfidence: 6,
      minEvidenceStrength: "moderate",
    });

    const duration = Date.now() - startTime;

    console.log("✅ Synthesis completed!\n");
    console.log("=".repeat(60));
    console.log(`⏱️  Duration: ${(duration / 1000).toFixed(1)}s`);
    console.log(`📊 Confidence Score: ${synthesis.confidence_score}/10\n`);

    console.log("📝 Executive Summary:");
    console.log(`   ${synthesis.executive_summary}\n`);

    console.log("🎯 Primary Strategy:");
    console.log(`   Name: ${synthesis.primary_strategy.name}`);
    console.log(`   Evidence Score: ${synthesis.primary_strategy.evidence_score}/10`);
    console.log(`   Sources: ${synthesis.primary_strategy.sources_count}`);
    console.log(`   Why Primary: ${synthesis.primary_strategy.why_primary}\n`);

    console.log(`🔄 Secondary Strategies: ${synthesis.secondary_strategies.length}`);
    synthesis.secondary_strategies.forEach((strat, idx) => {
      console.log(`   ${idx + 1}. ${strat.name} (${strat.evidence_score}/10)`);
      console.log(`      Use when: ${strat.use_case}`);
    });

    console.log(`\n🗺️  Market Conditions Map:`);
    console.log(`   Trending Up: ${synthesis.market_conditions_map.trending_up}`);
    console.log(`   Trending Down: ${synthesis.market_conditions_map.trending_down}`);
    console.log(`   Ranging: ${synthesis.market_conditions_map.ranging}`);
    console.log(`   High Volatility: ${synthesis.market_conditions_map.high_volatility}`);
    console.log(`   Low Volatility: ${synthesis.market_conditions_map.low_volatility}`);

    console.log(`\n❌ Avoid List: ${synthesis.avoid_list.length} items`);
    synthesis.avoid_list.forEach((item, idx) => {
      console.log(`   ${idx + 1}. ${item}`);
    });

    console.log(`\n💡 Common Patterns: ${synthesis.common_patterns?.length || 0}`);

    console.log(`\n⚠️  Limitations: ${synthesis.limitations.length}`);
    synthesis.limitations.forEach((lim, idx) => {
      console.log(`   ${idx + 1}. ${lim}`);
    });

    console.log(`\n📋 Risk Parameters:`);
    console.log(`   Max Position Size: ${synthesis.risk_parameters.max_position_size}`);
    console.log(`   Stop Loss: ${synthesis.risk_parameters.stop_loss_approach}`);
    console.log(`   Take Profit: ${synthesis.risk_parameters.take_profit_approach}`);
    console.log(`   Max Leverage: ${synthesis.risk_parameters.max_leverage}`);
    console.log(`   Max Drawdown: ${synthesis.risk_parameters.max_drawdown_tolerance}`);

    console.log("\n📖 Full Guide Preview (first 500 chars):");
    console.log(synthesis.full_guide_markdown.substring(0, 500) + "...\n");

    // Verify database
    console.log("🗄️  Verifying database records...\n");

    const { data: guide } = await supabase
      .from("trading_guides")
      .select("*")
      .order("version", { ascending: false })
      .limit(1)
      .single();

    if (!guide) {
      console.log("   ❌ Guide not found in database");
    } else {
      console.log(`   ✅ Guide created (Version ${guide.version})`);
      console.log(`      Based on ${guide.based_on_sources} sources`);
      console.log(`      Based on ${guide.based_on_strategies} strategies`);
      console.log(`      Confidence: ${guide.confidence_score}/10`);
    }

    const { data: logs } = await supabase
      .from("agent_logs")
      .select("*")
      .eq("agent_name", "synthesis")
      .order("created_at", { ascending: false })
      .limit(2);

    console.log(`   ✅ Agent logs: ${logs?.length || 0}`);
    logs?.forEach((log) => {
      console.log(`      - ${log.action}: ${log.status} (${log.duration_ms}ms)`);
      if (log.tokens_used) {
        console.log(
          `        Tokens: ${log.tokens_used}, Cost: $${log.estimated_cost_usd?.toFixed(6) || "0"}`
        );
      }
    });

    console.log("\n" + "=".repeat(60));
    console.log("✅ Synthesis Agent test completed successfully!\n");
  } catch (error) {
    console.error("\n💥 Synthesis failed:", error);
    process.exit(1);
  } finally {
    // Cleanup
    console.log("🧹 Cleaning up test data...");
    for (const sourceId of createdSourceIds) {
      await supabase.from("strategies_found").delete().eq("source_id", sourceId);
      await supabase
        .from("paper_extractions")
        .delete()
        .eq("source_id", sourceId);
      await supabase.from("agent_logs").delete().eq("source_id", sourceId);
      await supabase.from("sources").delete().eq("id", sourceId);
    }
    await supabase.from("trading_guides").delete().neq("version", 0);
    await supabase
      .from("agent_logs")
      .delete()
      .eq("agent_name", "synthesis");
    console.log("   Done!\n");
    process.exit(0);
  }
}

main().catch((error) => {
  console.error("\n💥 Test crashed:", error);
  process.exit(1);
});
