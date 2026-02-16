#!/usr/bin/env tsx
/**
 * Apply SQL migrations to Supabase
 *
 * Reads migration files from supabase/migrations/ and executes them in order.
 */

import { config } from "dotenv";
import { resolve } from "path";
import { readFileSync, readdirSync } from "fs";
import { join } from "path";
import { createServerClient } from "../lib/supabase";

config({ path: resolve(process.cwd(), ".env.local") });

async function main() {
  console.log("\n🔧 Applying Supabase migrations...\n");

  const supabase = createServerClient();
  const migrationsDir = join(process.cwd(), "supabase", "migrations");

  // Get all .sql files sorted by name
  const files = readdirSync(migrationsDir)
    .filter((f) => f.endsWith(".sql"))
    .sort();

  if (files.length === 0) {
    console.log("⚠️  No migration files found in supabase/migrations/");
    return;
  }

  for (const file of files) {
    console.log(`📄 Applying ${file}...`);
    const filePath = join(migrationsDir, file);
    const sql = readFileSync(filePath, "utf-8");

    try {
      // Execute the SQL (Supabase JS doesn't have a direct SQL exec method,
      // so we'll use the raw RPC approach or direct SQL via the REST API)
      const { error } = await supabase.rpc("exec_sql", { sql_string: sql });

      if (error) {
        // If exec_sql RPC doesn't exist, we need to use the SQL editor or CLI
        console.log(`   ⚠️  Cannot execute via JS client - use Supabase CLI or SQL editor`);
        console.log(`   💡 Run: supabase db push`);
        console.log(`   Or execute manually in Supabase SQL Editor`);
        return;
      }

      console.log(`   ✅ Applied ${file}`);
    } catch (error) {
      console.error(`   ❌ Error applying ${file}:`, error);
      throw error;
    }
  }

  console.log("\n✅ All migrations applied!\n");
}

main().catch((error) => {
  console.error("\n💥 Migration failed:", error);
  process.exit(1);
});
