#!/usr/bin/env tsx
/**
 * Test SSRF protection in safeFetch
 */

import { config } from "dotenv";
import { resolve } from "path";

config({ path: resolve(process.cwd(), ".env.local") });

async function main() {
  console.log("\n🛡️  Testing SSRF Protection...\n");

  const { safeFetch, FetchError } = await import("../lib/utils/fetcher");

  const maliciousUrls = [
    { url: "http://127.0.0.1", reason: "Localhost" },
    { url: "http://localhost", reason: "Localhost hostname" },
    { url: "http://169.254.169.254/latest/meta-data/", reason: "Cloud metadata" },
    { url: "http://10.0.0.1", reason: "Private IP 10.x" },
    { url: "http://192.168.1.1", reason: "Private IP 192.168.x" },
    { url: "http://172.16.0.1", reason: "Private IP 172.16-31.x" },
    { url: "file:///etc/passwd", reason: "File protocol" },
    { url: "ftp://example.com", reason: "FTP protocol" },
  ];

  let passed = 0;
  let failed = 0;

  for (const { url, reason } of maliciousUrls) {
    try {
      await safeFetch(url);
      console.log(`❌ FAILED to block ${reason}: ${url}`);
      failed++;
    } catch (error) {
      if (error instanceof FetchError) {
        console.log(`✅ Blocked ${reason}: ${error.code}`);
        passed++;
      } else {
        console.log(`⚠️  Unexpected error for ${reason}: ${error}`);
        failed++;
      }
    }
  }

  // Test valid URL (should work)
  console.log("\n🌐 Testing valid URL...");
  try {
    const result = await safeFetch("https://example.com");
    if (result.content && result.content.length > 0) {
      console.log(`✅ Valid URL works: fetched ${result.content.length} chars`);
      passed++;
    } else {
      console.log(`❌ Valid URL returned empty content`);
      failed++;
    }
  } catch (error) {
    console.log(`❌ Valid URL failed: ${error}`);
    failed++;
  }

  console.log("\n" + "=".repeat(60));
  console.log(`📊 Results: ${passed} passed, ${failed} failed\n`);

  if (failed > 0) {
    process.exit(1);
  } else {
    console.log("✅ All SSRF protection tests passed!\n");
    process.exit(0);
  }
}

main().catch((error) => {
  console.error("\n💥 Test crashed:", error);
  process.exit(1);
});
