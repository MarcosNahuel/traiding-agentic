#!/usr/bin/env tsx
/**
 * Test Chat Agent - RAG-based Q&A
 */

import { config } from "dotenv";
import { resolve } from "path";

config({ path: resolve(process.cwd(), ".env.local") });

async function main() {
  console.log("\n💬 Testing Chat Agent...\n");

  const { createServerClient } = await import("../lib/supabase");
  const { chat } = await import("../lib/agents/chat-agent");
  const { embed } = await import("ai");
  const { google } = await import("../lib/ai");
  const supabase = createServerClient();

  // Cleanup previous test data
  console.log("🧹 Cleaning up previous test data...");
  const { data: existingSources } = await supabase
    .from("sources")
    .select("id")
    .eq("url", "https://test-chat-agent.com");

  if (existingSources && existingSources.length > 0) {
    for (const src of existingSources) {
      await supabase.from("paper_chunks").delete().eq("source_id", src.id);
      await supabase.from("strategies_found").delete().eq("source_id", src.id);
      await supabase
        .from("paper_extractions")
        .delete()
        .eq("source_id", src.id);
      await supabase.from("sources").delete().eq("id", src.id);
    }
  }

  await supabase.from("trading_guides").delete().neq("version", 0);
  await supabase.from("chat_messages").delete().neq("id", "00000000-0000-0000-0000-000000000000");
  console.log("   Done\n");

  console.log("📄 Creating test data...\n");

  // Create test source
  const { data: source, error: sourceError } = await supabase
    .from("sources")
    .insert({
      url: "https://test-chat-agent.com",
      source_type: "paper",
      title: "RSI Trading Strategy for Bitcoin",
      authors: "Test Author",
      publication_year: 2024,
      status: "processed",
    })
    .select("id")
    .single();

  if (sourceError || !source) {
    console.error("❌ Failed to create source:", sourceError);
    process.exit(1);
  }

  console.log(`   ✅ Created source: ${source.id}`);

  // Create paper chunks with embeddings
  const chunks = [
    {
      content:
        "RSI (Relative Strength Index) is a momentum indicator that measures the speed and magnitude of price changes. When RSI drops below 30, it indicates oversold conditions and a potential buying opportunity.",
      section_title: "RSI Indicator Basics",
      chunk_index: 0,
    },
    {
      content:
        "Our backtest shows that buying BTC when RSI(14) < 30 and selling when RSI(14) > 70 produces a Sharpe ratio of 1.8 with 15% maximum drawdown over 3 years.",
      section_title: "Backtest Results",
      chunk_index: 1,
    },
    {
      content:
        "Risk management is critical. We recommend using a 3% stop-loss and position sizing of 2% of capital per trade to limit downside exposure.",
      section_title: "Risk Management",
      chunk_index: 2,
    },
  ];

  // Import truncation helper
  const { truncateEmbedding } = await import("../lib/utils/embeddings");

  for (const chunk of chunks) {
    // Generate embedding
    const { embedding: rawEmbedding } = await embed({
      model: google.embedding("gemini-embedding-001"),
      value: chunk.content,
    });

    // Truncate to 1024 dimensions
    const embedding = truncateEmbedding(rawEmbedding, 1024);

    const { error: chunkError } = await supabase.from("paper_chunks").insert({
      source_id: source.id,
      content: chunk.content,
      section_title: chunk.section_title,
      chunk_index: chunk.chunk_index,
      embedding: embedding,
    });

    if (chunkError) {
      console.error(`   ❌ Failed to create chunk ${chunk.chunk_index}:`, chunkError);
    } else {
      console.log(`   ✅ Created chunk: ${chunk.section_title}`);
    }
  }

  // Create extraction and strategy
  const { data: extraction } = await supabase
    .from("paper_extractions")
    .insert({
      source_id: source.id,
      executive_summary: "RSI-based momentum strategy for Bitcoin",
      confidence_score: 9,
    })
    .select("id")
    .single();

  const { error: stratError } = await supabase.from("strategies_found").insert({
    source_id: source.id,
    extraction_id: extraction!.id,
    name: "RSI Mean Reversion",
    description: "Buy oversold, sell overbought using RSI",
    strategy_type: "mean_reversion",
    market: "btc",
    timeframe: "4h",
    indicators: ["RSI(14)"],
    entry_rules: ["RSI < 30"],
    exit_rules: ["RSI > 70", "Stop loss at -3%"],
    confidence: 9,
    evidence_strength: "strong",
    backtest_results: {
      sharpe_ratio: 1.8,
      max_drawdown: 15,
    },
  });

  if (stratError) {
    console.error("   ❌ Failed to create strategy:", stratError);
  } else {
    console.log("   ✅ Created strategy: RSI Mean Reversion");
  }

  // Create trading guide
  const { error: guideError } = await supabase.from("trading_guides").insert({
    version: 1,
    based_on_sources: 1,
    based_on_strategies: 1,
    sources_used: [source.id],
    primary_strategy: {
      name: "RSI Mean Reversion",
      description: "Buy when RSI < 30, sell when RSI > 70",
      evidence_score: 9,
      why_primary: "Strong backtest results with Sharpe 1.8",
    },
    secondary_strategies: [],
    market_conditions_map: {
      ranging: "RSI Mean Reversion works best",
      trending: "Avoid RSI in strong trends",
    },
    avoid_list: ["Using RSI in trending markets"],
    risk_parameters: {
      max_position_size: "2% of capital",
      stop_loss_approach: "3% below entry",
    },
    full_guide_markdown: "# Trading Guide\n\nUse RSI for mean reversion...",
    system_prompt: "Test prompt",
    executive_summary:
      "Guide focused on RSI mean reversion strategy for Bitcoin trading",
    confidence_score: 9,
    limitations: ["Doesn't work in strong trends"],
  });

  if (guideError) {
    console.error("   ❌ Failed to create guide:", guideError);
  } else {
    console.log("   ✅ Created trading guide v1\n");
  }

  // Test questions
  const testQuestions = [
    {
      question: "¿Qué es el RSI y cómo se usa?",
      expectedKeywords: ["RSI", "momentum", "30", "70", "oversold"],
    },
    {
      question: "¿Cuáles son los resultados del backtest de la estrategia RSI?",
      expectedKeywords: ["Sharpe", "1.8", "drawdown", "15%"],
    },
    {
      question: "¿Cómo debería manejar el riesgo?",
      expectedKeywords: ["stop-loss", "3%", "2%", "capital"],
    },
  ];

  console.log("💬 Testing Chat Agent with questions...\n");

  for (let i = 0; i < testQuestions.length; i++) {
    const { question, expectedKeywords } = testQuestions[i];

    console.log(`\n📝 Question ${i + 1}: ${question}`);

    try {
      const startTime = Date.now();
      const response = await chat({
        message: question,
        includeGuide: true,
        includeStrategies: true,
        maxChunks: 3,
      });

      const duration = Date.now() - startTime;

      console.log(`\n✅ Answer generated (${(duration / 1000).toFixed(1)}s):`);
      console.log(`   ${response.answer.substring(0, 200)}...`);
      console.log(`\n📚 Sources used: ${response.sources.length}`);
      response.sources.forEach((source, idx) => {
        console.log(
          `   ${idx + 1}. [${source.type}] ${source.title}${source.similarity ? ` (${(source.similarity * 100).toFixed(1)}%)` : ""}`
        );
      });

      console.log(`\n📊 Metrics:`);
      console.log(`   Tokens: ${response.tokensUsed}`);
      console.log(`   Cost: $${response.cost.toFixed(6)}`);

      // Check if answer contains expected keywords
      const lowerAnswer = response.answer.toLowerCase();
      const foundKeywords = expectedKeywords.filter((kw) =>
        lowerAnswer.includes(kw.toLowerCase())
      );

      console.log(
        `\n🔍 Keywords: ${foundKeywords.length}/${expectedKeywords.length} found`
      );
      if (foundKeywords.length < expectedKeywords.length) {
        console.log(`   Missing: ${expectedKeywords.filter((kw) => !foundKeywords.includes(kw)).join(", ")}`);
      }
    } catch (error) {
      console.error(`\n❌ Failed to answer question: ${error}`);
    }
  }

  // Verify chat history
  console.log("\n🗄️  Verifying database records...\n");

  const { data: messages } = await supabase
    .from("chat_messages")
    .select("*")
    .order("created_at", { ascending: true });

  console.log(`   ✅ Chat messages stored: ${messages?.length || 0}`);
  if (messages && messages.length > 0) {
    const userMsgs = messages.filter((m) => m.role === "user").length;
    const assistantMsgs = messages.filter((m) => m.role === "assistant").length;
    console.log(`      User messages: ${userMsgs}`);
    console.log(`      Assistant messages: ${assistantMsgs}`);
  }

  const { data: logs } = await supabase
    .from("agent_logs")
    .select("*")
    .eq("agent_name", "chat")
    .order("created_at", { ascending: false })
    .limit(10);

  console.log(`   ✅ Agent logs: ${logs?.length || 0}`);
  logs?.forEach((log) => {
    console.log(
      `      - ${log.action}: ${log.status} (${log.duration_ms}ms, ${log.tokens_used || 0} tokens)`
    );
  });

  console.log("\n" + "=".repeat(60));
  console.log("✅ Chat Agent test completed successfully!\n");

  // Cleanup
  console.log("🧹 Cleaning up test data...");
  await supabase.from("paper_chunks").delete().eq("source_id", source.id);
  await supabase.from("strategies_found").delete().eq("source_id", source.id);
  await supabase.from("paper_extractions").delete().eq("source_id", source.id);
  await supabase.from("sources").delete().eq("id", source.id);
  await supabase.from("trading_guides").delete().eq("version", 1);
  await supabase.from("chat_messages").delete().neq("id", "00000000-0000-0000-0000-000000000000");
  await supabase.from("agent_logs").delete().eq("agent_name", "chat");
  console.log("   Done!\n");

  process.exit(0);
}

main().catch((error) => {
  console.error("\n💥 Test crashed:", error);
  process.exit(1);
});
