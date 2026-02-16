#!/usr/bin/env tsx
/**
 * Apply SQL migrations directly via Supabase REST API
 * This uses the Management API to execute SQL
 */

import { config } from "dotenv";
import { resolve } from "path";
import { readFileSync } from "fs";
import { join } from "path";

// Load environment variables
config({ path: resolve(process.cwd(), ".env.local") });

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!SUPABASE_URL || !SERVICE_ROLE_KEY) {
  console.error("❌ Missing Supabase credentials");
  process.exit(1);
}

// Extract project ref from URL (e.g., https://xxx.supabase.co -> xxx)
const projectRef = SUPABASE_URL.replace("https://", "").split(".")[0];

async function executeSql(sql: string): Promise<void> {
  // Use Supabase REST API with service role key
  const url = `${SUPABASE_URL}/rest/v1/rpc/exec`;

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "apikey": SERVICE_ROLE_KEY,
      "Authorization": `Bearer ${SERVICE_ROLE_KEY}`,
    },
    body: JSON.stringify({ query: sql }),
  });

  if (!response.ok) {
    // If RPC doesn't work, use the SQL endpoint directly
    // This requires posting to the database via the service role
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }
}

async function main() {
  console.log("\n🔧 Applying Supabase migrations via REST API...\n");
  console.log(`📍 Project: ${projectRef}`);
  console.log(`🔗 URL: ${SUPABASE_URL}\n`);

  const migrationsDir = join(process.cwd(), "supabase", "migrations");
  const migrations = [
    "001_initial_schema.sql",
    "002_pgvector_setup.sql",
  ];

  for (const file of migrations) {
    console.log(`📄 Reading ${file}...`);
    const filePath = join(migrationsDir, file);
    const sql = readFileSync(filePath, "utf-8");

    console.log(`⚙️  Executing ${file}...`);

    try {
      // Since Supabase doesn't have a direct SQL execution endpoint via REST API
      // for service role, we need to use the SQL Editor or CLI
      // Instead, let's use the Supabase client with raw SQL via supabase-js

      const { createClient } = await import("@supabase/supabase-js");
      const supabase = createClient(SUPABASE_URL, SERVICE_ROLE_KEY);

      // Split SQL into individual statements and execute one by one
      const statements = sql
        .split(";")
        .map(s => s.trim())
        .filter(s => s.length > 0 && !s.startsWith("--"));

      for (let i = 0; i < statements.length; i++) {
        const statement = statements[i];
        if (!statement) continue;

        // Use RPC to execute SQL (if available)
        // Note: This requires a custom RPC function in Supabase
        // For now, we'll need to use SQL Editor or CLI

        console.log(`   Statement ${i + 1}/${statements.length}...`);
      }

      console.log(`   ⚠️  Cannot execute SQL directly via JS client`);
      console.log(`   💡 Use Supabase SQL Editor or CLI instead`);
      console.log(`      SQL Editor: https://supabase.com/dashboard/project/${projectRef}/sql`);
      console.log(`      Or run: npx supabase db push\n`);

    } catch (error) {
      console.error(`   ❌ Error:`, error);
      throw error;
    }
  }

  console.log("\n⚠️  Manual step required:");
  console.log("   1. Go to: https://supabase.com/dashboard/project/" + projectRef + "/sql");
  console.log("   2. Create a new query");
  console.log("   3. Copy & paste the SQL from:");
  console.log("      - supabase/migrations/001_initial_schema.sql");
  console.log("      - supabase/migrations/002_pgvector_setup.sql");
  console.log("   4. Run each migration\n");
}

main().catch((error) => {
  console.error("\n💥 Failed:", error);
  process.exit(1);
});
