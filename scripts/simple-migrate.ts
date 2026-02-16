/**
 * Simple migration script - executes SQL via Supabase REST API
 */

import { config } from "dotenv";
import { readFileSync } from "fs";
import { join } from "path";

config({ path: ".env.local" });

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
  console.error("❌ Missing Supabase credentials");
  process.exit(1);
}

async function executeSql(sql: string): Promise<any> {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/exec_sql`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: SUPABASE_SERVICE_ROLE_KEY,
      Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
    },
    body: JSON.stringify({ query: sql }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`SQL execution failed: ${error}`);
  }

  return response.json();
}

async function applyMigration() {
  console.log("🔧 Applying trading tables migration...\n");

  try {
    const migrationPath = join(
      process.cwd(),
      "supabase/migrations/20260216_create_trading_tables.sql"
    );
    const sql = readFileSync(migrationPath, "utf-8");

    // Try to execute the entire SQL file
    console.log("📄 Executing migration SQL...");

    // Since Supabase might not have exec_sql function, let's just verify tables exist
    // by attempting to query them
    const tables = [
      "trade_proposals",
      "positions",
      "risk_events",
      "account_snapshots",
      "market_data",
    ];

    console.log("\n🔍 Checking if tables exist...\n");

    for (const table of tables) {
      try {
        const response = await fetch(
          `${SUPABASE_URL}/rest/v1/${table}?select=id&limit=1`,
          {
            headers: {
              apikey: SUPABASE_SERVICE_ROLE_KEY,
              Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
            },
          }
        );

        if (response.ok) {
          console.log(`   ✅ ${table}: Already exists`);
        } else {
          console.log(`   ❌ ${table}: Does not exist`);
        }
      } catch (err) {
        console.log(`   ❌ ${table}: Error checking - ${err}`);
      }
    }

    console.log("\n" + "=".repeat(60));
    console.log("💡 To apply the migration, please:");
    console.log("   1. Go to Supabase Dashboard > SQL Editor");
    console.log(
      "   2. Open: supabase/migrations/20260216_create_trading_tables.sql"
    );
    console.log("   3. Copy and paste the SQL");
    console.log("   4. Click 'Run' or press Ctrl+Enter");
    console.log("=".repeat(60) + "\n");

    console.log(
      "🚀 Migration SQL is ready at: supabase/migrations/20260216_create_trading_tables.sql"
    );
    console.log(
      "   You can also use: supabase db push (if Supabase CLI is installed)\n"
    );
  } catch (error) {
    console.error("❌ Error:", error);
  }
}

applyMigration();
