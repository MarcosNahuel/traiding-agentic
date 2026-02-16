#!/usr/bin/env tsx
/**
 * Verification script for Fase 0 - Foundation
 *
 * Checks:
 * 1. Environment variables
 * 2. Supabase connection + tables
 * 3. pgvector + HNSW index
 * 4. RPC match_chunks function
 * 5. Embedding generation (1024 dims)
 * 6. RLS policies
 * 7. Fetcher SSRF protection
 * 8. Telegram Bot (optional)
 */

import { config } from "dotenv";
import { resolve } from "path";

// Load environment variables from .env.local FIRST
config({ path: resolve(process.cwd(), ".env.local") });

interface TestResult {
  name: string;
  status: "pass" | "fail" | "skip";
  message?: string;
  duration?: number;
}

const results: TestResult[] = [];

function logTest(name: string, status: "pass" | "fail" | "skip", message?: string, duration?: number) {
  results.push({ name, status, message, duration });

  const emoji = status === "pass" ? "✅" : status === "fail" ? "❌" : "⏭️";
  const color = status === "pass" ? "\x1b[32m" : status === "fail" ? "\x1b[31m" : "\x1b[33m";
  const reset = "\x1b[0m";

  console.log(`${emoji} ${color}${name}${reset}${message ? ` - ${message}` : ""}`);
}

async function runTest(name: string, fn: () => Promise<void>): Promise<void> {
  const start = Date.now();
  try {
    await fn();
    const duration = Date.now() - start;
    logTest(name, "pass", `(${duration}ms)`, duration);
  } catch (error) {
    const duration = Date.now() - start;
    const message = error instanceof Error ? error.message : JSON.stringify(error);
    logTest(name, "fail", message, duration);
  }
}

async function main() {
  console.log("\n🔍 Starting Fase 0 verification...\n");

  // Dynamic imports after env vars are loaded
  const { createServerClient } = await import("../lib/supabase");
  const { embed } = await import("ai");
  const { google } = await import("../lib/ai");
  const { safeFetch, FetchError } = await import("../lib/utils/fetcher");
  const { sendAlert } = await import("../lib/utils/telegram");

  // 1. Environment variables
  await runTest("Environment: GOOGLE_AI_API_KEY", async () => {
    if (!process.env.GOOGLE_AI_API_KEY) {
      throw new Error("Missing GOOGLE_AI_API_KEY");
    }
  });

  await runTest("Environment: NEXT_PUBLIC_SUPABASE_URL", async () => {
    if (!process.env.NEXT_PUBLIC_SUPABASE_URL) {
      throw new Error("Missing NEXT_PUBLIC_SUPABASE_URL");
    }
  });

  await runTest("Environment: SUPABASE_SERVICE_ROLE_KEY", async () => {
    if (!process.env.SUPABASE_SERVICE_ROLE_KEY) {
      throw new Error("Missing SUPABASE_SERVICE_ROLE_KEY");
    }
  });

  // 2. Supabase connection
  let supabase: ReturnType<typeof createServerClient> | null = null;
  await runTest("Supabase: Connection", async () => {
    supabase = createServerClient();
    const { data, error } = await supabase.from("sources").select("count");
    if (error) throw error;
  });

  if (!supabase) {
    console.log("\n❌ Cannot continue without Supabase connection\n");
    process.exit(1);
  }

  // 3. Check all tables exist
  const tables = [
    "sources",
    "paper_extractions",
    "strategies_found",
    "paper_chunks",
    "trading_guides",
    "agent_logs",
    "chat_messages",
  ];

  for (const table of tables) {
    await runTest(`Supabase: Table '${table}' exists`, async () => {
      const { error } = await supabase!.from(table).select("count").limit(0);
      if (error) throw error;
    });
  }

  // 4. pgvector extension
  await runTest("pgvector: Extension enabled", async () => {
    const { data, error } = await supabase!.rpc("match_chunks", {
      query_embedding: Array(1024).fill(0),
      match_threshold: 0.9,
      match_count: 1,
    });
    if (error) throw error;
  });

  // 5. Test embedding generation
  await runTest("AI SDK: Generate embedding (1024 dims)", async () => {
    const { embedding } = await embed({
      model: google.embedding("gemini-embedding-001"),
      value: "test de embedding para trading bot",
      providerOptions: {
        google: { outputDimensionality: 1024 },
      },
    });

    if (embedding.length !== 1024) {
      throw new Error(`Expected 1024 dims, got ${embedding.length}`);
    }
  });

  // 6. Test vector storage and search
  await runTest("pgvector: Insert + search with HNSW", async () => {
    const testContent = "Bitcoin momentum strategy using RSI indicator";

    // Generate embedding
    const { embedding } = await embed({
      model: google.embedding("gemini-embedding-001"),
      value: testContent,
      providerOptions: {
        google: { outputDimensionality: 1024 },
      },
    });

    // Create test source
    const { data: source, error: sourceError } = await supabase!
      .from("sources")
      .insert({
        url: `https://test.example.com/test-${Date.now()}`,
        source_type: "paper",
        title: "Test Paper",
      })
      .select("id")
      .single();

    if (sourceError) throw sourceError;

    // Insert chunk with embedding
    const { error: chunkError } = await supabase!.from("paper_chunks").insert({
      source_id: source.id,
      chunk_index: 0,
      content: testContent,
      embedding: embedding,
    });

    if (chunkError) throw chunkError;

    // Search for similar chunks
    const { data: matches, error: searchError } = await supabase!.rpc(
      "match_chunks",
      {
        query_embedding: embedding,
        match_threshold: 0.9,
        match_count: 1,
      }
    );

    if (searchError) throw searchError;
    if (!matches || matches.length === 0) {
      throw new Error("No matches found for inserted chunk");
    }

    // Cleanup
    await supabase!.from("sources").delete().eq("id", source.id);
  });

  // 7. Test RLS policies
  await runTest("RLS: Service role has full access", async () => {
    const { error } = await supabase!
      .from("sources")
      .select("*")
      .limit(1);
    if (error) throw error;
  });

  // 8. Test fetcher SSRF protection
  await runTest("Fetcher: Blocks private IPs (127.0.0.1)", async () => {
    try {
      await safeFetch("http://127.0.0.1");
      throw new Error("Should have blocked private IP");
    } catch (error) {
      if (!(error instanceof FetchError && error.code === "BLOCKED_HOST")) {
        throw new Error(`Wrong error: ${error}`);
      }
    }
  });

  await runTest("Fetcher: Blocks metadata endpoint", async () => {
    try {
      await safeFetch("http://169.254.169.254");
      throw new Error("Should have blocked metadata endpoint");
    } catch (error) {
      if (!(error instanceof FetchError && error.code === "BLOCKED_HOST")) {
        throw new Error(`Wrong error: ${error}`);
      }
    }
  });

  await runTest("Fetcher: Blocks invalid protocol", async () => {
    try {
      await safeFetch("file:///etc/passwd");
      throw new Error("Should have blocked file:// protocol");
    } catch (error) {
      if (!(error instanceof FetchError && error.code === "BLOCKED_PROTOCOL")) {
        throw new Error(`Wrong error: ${error}`);
      }
    }
  });

  // 9. Telegram (optional)
  if (process.env.TELEGRAM_BOT_TOKEN && process.env.TELEGRAM_CHAT_ID) {
    await runTest("Telegram: Send test message", async () => {
      await sendAlert("✅ Sistema de verificación completado correctamente");
    });
  } else {
    logTest("Telegram: Send test message", "skip", "No credentials configured");
  }

  // Summary
  console.log("\n" + "=".repeat(60));
  const passed = results.filter((r) => r.status === "pass").length;
  const failed = results.filter((r) => r.status === "fail").length;
  const skipped = results.filter((r) => r.status === "skip").length;

  console.log(`\n📊 Results: ${passed} passed, ${failed} failed, ${skipped} skipped`);

  if (failed > 0) {
    console.log("\n❌ Verification FAILED - fix errors above\n");
    process.exit(1);
  } else {
    console.log("\n✅ All checks passed! Fase 0 is complete.\n");
    process.exit(0);
  }
}

main().catch((error) => {
  console.error("\n💥 Verification script crashed:", error);
  process.exit(1);
});
