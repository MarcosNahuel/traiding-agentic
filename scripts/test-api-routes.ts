#!/usr/bin/env tsx
/**
 * Test script for Source Agent API routes
 * Tests all endpoints and edge cases
 */

import { config } from "dotenv";
import { resolve } from "path";

// Load environment variables
config({ path: resolve(process.cwd(), ".env.local") });

interface TestResult {
  name: string;
  status: "pass" | "fail";
  message?: string;
  duration?: number;
}

const results: TestResult[] = [];
let baseUrl: string;

function logTest(name: string, status: "pass" | "fail", message?: string, duration?: number) {
  results.push({ name, status, message, duration });

  const emoji = status === "pass" ? "✅" : "❌";
  const color = status === "pass" ? "\x1b[32m" : "\x1b[31m";
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
  console.log("\n🧪 Testing Source Agent API Routes...\n");

  // Dynamic imports
  const { createServerClient } = await import("../lib/supabase");
  const supabase = createServerClient();

  // Start dev server for API testing
  console.log("🚀 Starting Next.js dev server...\n");
  const { spawn } = await import("child_process");

  const server = spawn("npm", ["run", "dev"], {
    stdio: ["ignore", "pipe", "pipe"],
    shell: true,
  });

  // Wait for server to be ready
  await new Promise<void>((resolve) => {
    let output = "";
    server.stdout?.on("data", (data) => {
      output += data.toString();
      if (output.includes("Local:") || output.includes("localhost:3000")) {
        // Extract port from output
        const match = output.match(/localhost:(\d+)/);
        const port = match ? match[1] : "3000";
        baseUrl = `http://localhost:${port}`;
        console.log(`✅ Server ready at ${baseUrl}\n`);
        setTimeout(resolve, 2000); // Give it 2s to fully initialize
      }
    });
  });

  try {
    // Test 1: POST /api/sources - Valid paper
    await runTest("POST /api/sources - Valid paper URL", async () => {
      const testUrl = `https://arxiv.org/abs/test-${Date.now()}`;

      const response = await fetch(`${baseUrl}/api/sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: testUrl,
          sourceType: "paper",
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      }

      const data = await response.json();
      if (
        !data.sourceId ||
        !["pending", "completed"].includes(data.status)
      ) {
        throw new Error(`Invalid response: ${JSON.stringify(data)}`);
      }

      // Cleanup
      await supabase.from("sources").delete().eq("id", data.sourceId);
    });

    // Test 2: POST /api/sources - Missing URL
    await runTest("POST /api/sources - Missing URL (should fail)", async () => {
      const response = await fetch(`${baseUrl}/api/sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sourceType: "paper",
        }),
      });

      if (response.status !== 400) {
        throw new Error(`Expected 400, got ${response.status}`);
      }

      const data = await response.json();
      if (!data.error || !data.error.includes("URL")) {
        throw new Error(`Wrong error message: ${JSON.stringify(data)}`);
      }
    });

    // Test 3: POST /api/sources - Invalid source type
    await runTest("POST /api/sources - Invalid source type (should fail)", async () => {
      const response = await fetch(`${baseUrl}/api/sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: "https://example.com",
          sourceType: "invalid",
        }),
      });

      if (response.status !== 400) {
        throw new Error(`Expected 400, got ${response.status}`);
      }

      const data = await response.json();
      if (!data.error || !data.error.includes("sourceType")) {
        throw new Error(`Wrong error message: ${JSON.stringify(data)}`);
      }
    });

    // Test 4: POST /api/sources - Duplicate URL
    await runTest("POST /api/sources - Duplicate URL (should return 409)", async () => {
      const testUrl = `https://arxiv.org/abs/dup-${Date.now()}`;

      // Create first source
      const { data: source } = await supabase
        .from("sources")
        .insert({ url: testUrl, source_type: "paper" })
        .select("id")
        .single();

      try {
        const response = await fetch(`${baseUrl}/api/sources`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url: testUrl,
            sourceType: "paper",
          }),
        });

        if (response.status !== 409) {
          throw new Error(`Expected 409, got ${response.status}`);
        }

        const data = await response.json();
        if (!data.error || !data.error.includes("already exists")) {
          throw new Error(`Wrong error message: ${JSON.stringify(data)}`);
        }
      } finally {
        // Cleanup
        await supabase.from("sources").delete().eq("id", source!.id);
      }
    });

    // Test 5: GET /api/sources - List sources
    await runTest("GET /api/sources - List sources", async () => {
      const response = await fetch(`${baseUrl}/api/sources`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      }

      const data = await response.json();
      if (!Array.isArray(data.sources) || typeof data.total !== "number") {
        throw new Error(`Invalid response structure: ${JSON.stringify(data)}`);
      }
    });

    // Test 6: GET /api/sources - Filter by status
    await runTest("GET /api/sources?status=approved - Filter by status", async () => {
      const response = await fetch(`${baseUrl}/api/sources?status=approved`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      }

      const data = await response.json();
      if (!Array.isArray(data.sources)) {
        throw new Error(`Invalid response: ${JSON.stringify(data)}`);
      }

      // Verify all sources have status=approved
      const wrongStatus = data.sources.find((s: any) => s.status !== "approved");
      if (wrongStatus) {
        throw new Error(`Found source with wrong status: ${wrongStatus.status}`);
      }
    });

    // Test 7: GET /api/sources - Pagination
    await runTest("GET /api/sources?limit=5&offset=0 - Pagination", async () => {
      const response = await fetch(`${baseUrl}/api/sources?limit=5&offset=0`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      }

      const data = await response.json();
      if (!Array.isArray(data.sources) || data.limit !== 5 || data.offset !== 0) {
        throw new Error(`Invalid pagination: ${JSON.stringify(data)}`);
      }
    });

    // Test 8: GET /api/sources/[id] - Get single source
    await runTest("GET /api/sources/[id] - Get source by ID", async () => {
      // Create test source
      const { data: source } = await supabase
        .from("sources")
        .insert({
          url: `https://test-${Date.now()}.com`,
          source_type: "paper",
          title: "Test Paper",
        })
        .select("id")
        .single();

      try {
        const response = await fetch(`${baseUrl}/api/sources/${source!.id}`);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }

        const data = await response.json();
        if (!data.source || data.source.id !== source!.id) {
          throw new Error(`Invalid response: ${JSON.stringify(data)}`);
        }
      } finally {
        // Cleanup
        await supabase.from("sources").delete().eq("id", source!.id);
      }
    });

    // Test 9: GET /api/sources/[id] - Non-existent ID
    await runTest("GET /api/sources/[id] - Non-existent ID (should 404)", async () => {
      const fakeId = "00000000-0000-0000-0000-000000000000";
      const response = await fetch(`${baseUrl}/api/sources/${fakeId}`);

      if (response.status !== 404) {
        throw new Error(`Expected 404, got ${response.status}`);
      }

      const data = await response.json();
      if (!data.error || !data.error.includes("not found")) {
        throw new Error(`Wrong error message: ${JSON.stringify(data)}`);
      }
    });

    // Test 10: POST /api/sources/[id]/evaluate - Manual evaluation
    await runTest("POST /api/sources/[id]/evaluate - Manual trigger", async () => {
      // Create test source with content
      const { data: source, error: insertError } = await supabase
        .from("sources")
        .insert({
          url: `https://test-${Date.now()}.com`,
          source_type: "paper",
          raw_content: "Bitcoin momentum trading strategy using RSI indicator for entry and exit signals. Backtest shows Sharpe ratio of 1.5 over 2 years.",
        })
        .select("id")
        .single();

      if (insertError || !source) {
        throw new Error(`Failed to create test source: ${insertError?.message || "Unknown error"}`);
      }

      try {
        const response = await fetch(`${baseUrl}/api/sources/${source!.id}/evaluate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }

        const data = await response.json();
        if (!data.success || !data.evaluation) {
          throw new Error(`Invalid response: ${JSON.stringify(data)}`);
        }

        // Verify evaluation has required fields
        const eval_ = data.evaluation;
        if (
          !eval_.title ||
          typeof eval_.overall_score !== "number" ||
          !eval_.decision
        ) {
          throw new Error(`Missing evaluation fields: ${JSON.stringify(eval_)}`);
        }
      } finally {
        // Cleanup
        await supabase.from("agent_logs").delete().eq("source_id", source!.id);
        await supabase.from("sources").delete().eq("id", source!.id);
      }
    });

    // Test 11: POST /api/sources/[id]/evaluate - No content
    await runTest("POST /api/sources/[id]/evaluate - No content (should fail)", async () => {
      // Create source without content
      const { data: source } = await supabase
        .from("sources")
        .insert({
          url: `https://test-${Date.now()}.com`,
          source_type: "paper",
        })
        .select("id")
        .single();

      try {
        const response = await fetch(`${baseUrl}/api/sources/${source!.id}/evaluate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });

        if (response.status !== 400) {
          throw new Error(`Expected 400, got ${response.status}`);
        }

        const data = await response.json();
        if (!data.error || !data.error.includes("no content")) {
          throw new Error(`Wrong error message: ${JSON.stringify(data)}`);
        }
      } finally {
        // Cleanup
        await supabase.from("sources").delete().eq("id", source!.id);
      }
    });

    // Summary
    console.log("\n" + "=".repeat(60));
    const passed = results.filter((r) => r.status === "pass").length;
    const failed = results.filter((r) => r.status === "fail").length;

    console.log(`\n📊 Results: ${passed} passed, ${failed} failed`);

    if (failed > 0) {
      console.log("\n❌ Some tests FAILED\n");
      process.exit(1);
    } else {
      console.log("\n✅ All API route tests passed!\n");
      process.exit(0);
    }
  } finally {
    // Kill server
    console.log("\n🛑 Stopping dev server...");
    server.kill();
  }
}

main().catch((error) => {
  console.error("\n💥 Test script crashed:", error);
  process.exit(1);
});
