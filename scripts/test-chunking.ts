#!/usr/bin/env tsx
/**
 * Test paper chunking and embedding generation
 */

import { config } from "dotenv";
import { resolve } from "path";

config({ path: resolve(process.cwd(), ".env.local") });

const testPaper = `
ABSTRACT

Bitcoin trading strategies have gained significant attention in recent years. This paper explores momentum-based approaches using technical indicators.

INTRODUCTION

The cryptocurrency market presents unique challenges for algorithmic trading. Unlike traditional markets, Bitcoin operates 24/7 and exhibits high volatility. This creates both opportunities and risks for traders.

METHODOLOGY

We tested three technical indicators:
1. RSI (Relative Strength Index)
2. MACD (Moving Average Convergence Divergence)
3. Bollinger Bands

Our backtest covered the period from 2020 to 2023 using data from Binance exchange. We used 4-hour candles and implemented strict risk management rules.

RESULTS

The RSI-based strategy performed best with a Sharpe ratio of 1.8 and maximum drawdown of 15%. Entry signals occurred when RSI dropped below 30, and exits when it rose above 70.

The MACD strategy showed a Sharpe ratio of 1.5 with 18% drawdown. Bollinger Band breakouts had mixed results, working well in trending markets but generating false signals during consolidation.

RISK MANAGEMENT

We recommend the following risk parameters:
- Position size: 2% of capital per trade
- Stop loss: 3% below entry
- Maximum leverage: 2x
- Daily loss limit: 5% of capital

CONCLUSION

Technical indicators can be effective for Bitcoin trading when combined with proper risk management. The RSI-based approach showed the most consistent results across different market conditions.

REFERENCES

Martinez et al. (2022) - Cryptocurrency Trading Strategies
Chen (2021) - Technical Analysis in Digital Assets
`;

async function main() {
  console.log("\n📄 Testing Paper Chunking...\n");

  const { createServerClient } = await import("../lib/supabase");
  const { chunkAndEmbedPaper } = await import("../lib/services/chunk-paper");
  const { chunkPaper } = await import("../lib/utils/chunking");
  const supabase = createServerClient();

  // Test 1: Basic chunking without database
  console.log("1️⃣ Testing text chunking (no DB)...\n");

  const chunks = chunkPaper(testPaper, {
    maxChunkSize: 500,
    overlap: 100,
    preserveParagraphs: true,
  });

  console.log(`   ✅ Created ${chunks.length} chunks`);
  chunks.forEach((chunk, idx) => {
    console.log(`   Chunk ${idx}: ${chunk.content.length} chars${chunk.sectionTitle ? `, Section: ${chunk.sectionTitle}` : ""}`);
  });

  // Test 2: Full chunking with embeddings
  console.log("\n2️⃣ Testing chunking with embeddings (DB)...\n");

  // Cleanup existing test data
  const { data: existingSources } = await supabase
    .from("sources")
    .select("id")
    .eq("url", "https://test-chunking.com");

  if (existingSources && existingSources.length > 0) {
    for (const src of existingSources) {
      await supabase.from("paper_chunks").delete().eq("source_id", src.id);
      await supabase.from("sources").delete().eq("id", src.id);
    }
  }

  // Create test source
  const { data: source, error: sourceError } = await supabase
    .from("sources")
    .insert({
      url: "https://test-chunking.com",
      source_type: "paper",
      title: "Bitcoin Trading Strategies Test Paper",
      status: "approved",
      raw_content: testPaper,
    })
    .select("id")
    .single();

  if (sourceError || !source) {
    console.error("   ❌ Failed to create source:", sourceError);
    process.exit(1);
  }

  console.log(`   ✅ Created source: ${source.id}`);

  // Chunk and embed
  const result = await chunkAndEmbedPaper({
    sourceId: source.id,
    content: testPaper,
    maxChunkSize: 500,
    overlap: 100,
  });

  console.log(`\n   ✅ Chunking completed:`);
  console.log(`      Chunks created: ${result.chunksCreated}`);
  console.log(`      Total characters: ${result.totalCharacters}`);
  console.log(`      Duration: ${(result.duration / 1000).toFixed(1)}s`);
  console.log(`      Estimated cost: $${result.cost.toFixed(6)}`);

  // Test 3: Verify chunks in database
  console.log("\n3️⃣ Verifying chunks in database...\n");

  const { data: storedChunks, error: chunksError } = await supabase
    .from("paper_chunks")
    .select("*")
    .eq("source_id", source.id)
    .order("chunk_index", { ascending: true });

  if (chunksError) {
    console.error("   ❌ Failed to fetch chunks:", chunksError);
  } else {
    console.log(`   ✅ Found ${storedChunks?.length || 0} chunks in database`);
    storedChunks?.forEach((chunk: any) => {
      console.log(
        `      Chunk ${chunk.chunk_index}: ${chunk.content.length} chars, embedding: ${chunk.embedding ? chunk.embedding.length : 0} dims${chunk.section_title ? `, Section: ${chunk.section_title}` : ""}`
      );
    });
  }

  // Test 4: Test vector search
  console.log("\n4️⃣ Testing vector search...\n");

  const { embed } = await import("ai");
  const { google } = await import("../lib/ai");
  const { truncateEmbedding } = await import("../lib/utils/embeddings");

  const testQuery = "What are the backtest results for RSI strategy?";
  console.log(`   Query: "${testQuery}"`);

  // Generate query embedding
  const { embedding: rawQueryEmbedding } = await embed({
    model: google.embedding("gemini-embedding-001"),
    value: testQuery,
  });

  const queryEmbedding = truncateEmbedding(rawQueryEmbedding, 1024);

  // Search for similar chunks
  const { data: searchResults, error: searchError } = await supabase.rpc(
    "match_chunks",
    {
      query_embedding: queryEmbedding,
      match_threshold: 0.5,
      match_count: 3,
    }
  );

  if (searchError) {
    console.error("   ❌ Search failed:", searchError);
  } else {
    console.log(`   ✅ Found ${searchResults?.length || 0} matching chunks:\n`);
    searchResults?.forEach((result: any, idx: number) => {
      console.log(`   ${idx + 1}. Similarity: ${(result.similarity * 100).toFixed(1)}%`);
      console.log(`      Section: ${result.section_title || "N/A"}`);
      console.log(`      Content: ${result.content.substring(0, 150)}...`);
      console.log("");
    });
  }

  console.log("=" .repeat(60));
  console.log("✅ Chunking test completed successfully!\n");

  // Cleanup
  console.log("🧹 Cleaning up test data...");
  await supabase.from("paper_chunks").delete().eq("source_id", source.id);
  await supabase.from("sources").delete().eq("id", source.id);
  console.log("   Done!\n");

  process.exit(0);
}

main().catch((error) => {
  console.error("\n💥 Test crashed:", error);
  process.exit(1);
});
