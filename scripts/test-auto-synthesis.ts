#!/usr/bin/env tsx
/**
 * Test auto-synthesis trigger functionality
 */

import { config } from "dotenv";
import { resolve } from "path";

config({ path: resolve(process.cwd(), ".env.local") });

async function main() {
  console.log("\n🤖 Testing Auto-Synthesis Trigger...\n");

  const {
    checkAndTriggerSynthesis,
    getAutoSynthesisStatus,
  } = await import("../lib/services/auto-synthesis");

  // Test 1: Check current status
  console.log("1️⃣ Checking auto-synthesis status...\n");

  const status = await getAutoSynthesisStatus();

  console.log(`   Last synthesis: ${status.lastSynthesis?.toLocaleString() || "Never"}`);
  console.log(
    `   New papers since: ${status.newPapersSinceLastSynthesis}`
  );
  console.log(`   Threshold: ${status.threshold}`);
  console.log(
    `   Ready to trigger: ${status.readyToTrigger ? "✅ YES" : "❌ NO"}`
  );

  // Test 2: Check if synthesis should trigger
  console.log("\n2️⃣ Testing auto-trigger logic...\n");

  const result = await checkAndTriggerSynthesis({
    threshold: 5, // Use default threshold
    enabled: true,
  });

  if (result.triggered) {
    console.log(`   ✅ Synthesis triggered!`);
    console.log(`   Reason: ${result.reason}`);
  } else {
    console.log(`   ℹ️  Synthesis NOT triggered`);
    console.log(`   Reason: ${result.reason}`);
  }

  // Test 3: Test with lower threshold to force trigger
  console.log("\n3️⃣ Testing with threshold = 1 (force trigger)...\n");

  const forcedResult = await checkAndTriggerSynthesis({
    threshold: 1,
    enabled: true,
  });

  if (forcedResult.triggered) {
    console.log(`   ✅ Synthesis triggered with low threshold!`);
    console.log(`   Reason: ${forcedResult.reason}`);
  } else {
    console.log(`   ℹ️  Synthesis NOT triggered`);
    console.log(`   Reason: ${forcedResult.reason}`);
    console.log(
      `   (This is expected if there are no processed papers in the database)`
    );
  }

  // Test 4: Test with disabled auto-synthesis
  console.log("\n4️⃣ Testing with auto-synthesis disabled...\n");

  const disabledResult = await checkAndTriggerSynthesis({
    threshold: 1,
    enabled: false,
  });

  console.log(`   ${disabledResult.triggered ? "❌" : "✅"} Correctly ${disabledResult.triggered ? "triggered (BUG!)" : "skipped"}`);
  console.log(`   Reason: ${disabledResult.reason}`);

  // Summary
  console.log("\n" + "=".repeat(60));
  console.log("✅ Auto-synthesis test completed!\n");

  process.exit(0);
}

main().catch((error) => {
  console.error("\n💥 Test failed:", error);
  process.exit(1);
});
