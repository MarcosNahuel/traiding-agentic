#!/usr/bin/env tsx
/**
 * Test script for Source Agent
 * Tests the complete flow: add source -> fetch -> evaluate
 */

import { config } from "dotenv";
import { resolve } from "path";

// Load environment variables
config({ path: resolve(process.cwd(), ".env.local") });

async function main() {
  console.log("\n🧪 Testing Source Agent...\n");

  // Dynamic imports after env vars are loaded
  const { createServerClient } = await import("../lib/supabase");
  const { safeFetch } = await import("../lib/utils/fetcher");
  const { evaluateSource } = await import("../lib/agents/source-agent");

  const supabase = createServerClient();

  // Test URL - a real trading paper (public arXiv paper)
  const testUrl = "https://arxiv.org/abs/2106.00123";
  const testType = "paper";

  console.log(`📄 Test source: ${testUrl}`);
  console.log(`📋 Type: ${testType}\n`);

  // Step 0: Clean up any existing test entries
  console.log("0️⃣ Cleaning up existing test entries...");

  // First, find existing source
  const { data: existingSources } = await supabase
    .from("sources")
    .select("id")
    .eq("url", testUrl);

  if (existingSources && existingSources.length > 0) {
    for (const src of existingSources) {
      // Delete agent_logs first (foreign key constraint)
      await supabase.from("agent_logs").delete().eq("source_id", src.id);

      // Now delete source
      await supabase.from("sources").delete().eq("id", src.id);
    }
    console.log(`✅ Deleted ${existingSources.length} existing entries with their logs`);
  } else {
    console.log("✅ No existing entries to clean");
  }
  console.log();

  // Step 1: Create source in DB
  console.log("1️⃣ Creating source in database...");
  const { data: source, error: insertError } = await supabase
    .from("sources")
    .insert({
      url: testUrl,
      source_type: testType,
      status: "pending",
    })
    .select("id")
    .single();

  if (insertError) {
    console.error("❌ Failed to create source:", insertError);
    process.exit(1);
  }

  console.log(`✅ Source created with ID: ${source.id}\n`);

  // Step 2: Fetch content
  console.log("2️⃣ Fetching content...");
  try {
    await supabase
      .from("sources")
      .update({ status: "fetching", updated_at: new Date().toISOString() })
      .eq("id", source.id);

    const result = await safeFetch(testUrl);
    const rawContent = result.content;
    console.log(`✅ Fetched ${rawContent.length} characters\n`);

    await supabase
      .from("sources")
      .update({
        raw_content: rawContent.slice(0, 100000),
        content_length: rawContent.length,
        fetched_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq("id", source.id);

    // Step 3: Evaluate
    console.log("3️⃣ Evaluating source with Source Agent...");
    const evaluation = await evaluateSource({
      sourceId: source.id,
      url: testUrl,
      rawContent,
      sourceType: testType,
    });

    console.log("\n📊 Evaluation Results:");
    console.log("─".repeat(60));
    console.log(`Title: ${evaluation.title}`);
    console.log(`Authors: ${evaluation.authors || "N/A"}`);
    console.log(`Year: ${evaluation.publication_year || "N/A"}`);
    console.log("\n📈 Scores:");
    console.log(`  Relevance:      ${evaluation.relevance_score}/10`);
    console.log(`  Credibility:    ${evaluation.credibility_score}/10`);
    console.log(`  Applicability:  ${evaluation.applicability_score}/10`);
    console.log(`  Overall:        ${evaluation.overall_score}/10`);
    console.log(`\n✨ Decision: ${evaluation.decision.toUpperCase()}`);

    if (evaluation.decision === "rejected") {
      console.log(`❌ Rejection reason: ${evaluation.rejection_reason}`);
    }

    console.log(`\n🏷️  Tags: ${evaluation.tags.join(", ")}`);
    console.log(`\n📝 Summary:\n${evaluation.summary}`);
    console.log(`\n🤔 Reasoning:\n${evaluation.evaluation_reasoning}`);

    // Step 4: Verify in DB
    console.log("\n4️⃣ Verifying database update...");
    const { data: updatedSource, error: fetchError } = await supabase
      .from("sources")
      .select("*")
      .eq("id", source.id)
      .single();

    if (fetchError) {
      console.error("❌ Failed to fetch updated source:", fetchError);
      process.exit(1);
    }

    console.log(`✅ Status in DB: ${updatedSource.status}`);
    console.log(`✅ Overall score in DB: ${updatedSource.overall_score}/10`);

    // Step 5: Check agent logs
    console.log("\n5️⃣ Checking agent logs...");
    const { data: logs, error: logsError } = await supabase
      .from("agent_logs")
      .select("*")
      .eq("source_id", source.id)
      .order("created_at", { ascending: false });

    if (logsError) {
      console.error("❌ Failed to fetch logs:", logsError);
    } else {
      console.log(`✅ Found ${logs.length} log entries`);
      logs.forEach((log, i) => {
        console.log(
          `   ${i + 1}. ${log.action} - ${log.status} (${log.duration_ms}ms)`
        );
        if (log.tokens_used) {
          console.log(`      Tokens: ${log.tokens_used}, Cost: $${log.estimated_cost_usd?.toFixed(6)}`);
        }
      });
    }

    console.log("\n" + "=".repeat(60));
    console.log("✅ Source Agent test completed successfully!\n");

    // Cleanup (optional - comment out to keep test data)
    console.log("🧹 Cleaning up test data...");
    await supabase.from("agent_logs").delete().eq("source_id", source.id);
    await supabase.from("sources").delete().eq("id", source.id);
    console.log("✅ Cleanup complete\n");

    process.exit(0);
  } catch (error) {
    console.error("\n❌ Test failed:", error);

    // Update source with error
    await supabase
      .from("sources")
      .update({
        status: "error",
        error_message: error instanceof Error ? error.message : String(error),
        updated_at: new Date().toISOString(),
      })
      .eq("id", source.id);

    process.exit(1);
  }
}

main().catch((error) => {
  console.error("\n💥 Test script crashed:", error);
  process.exit(1);
});
