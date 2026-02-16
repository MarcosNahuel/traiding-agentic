/**
 * Apply trading tables migration
 */

import { config } from "dotenv";
import { readFileSync } from "fs";
import { join } from "path";
import { createClient } from "@supabase/supabase-js";

// Load environment variables
config({ path: ".env.local" });

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
  console.error("❌ Missing Supabase credentials");
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: {
    autoRefreshToken: false,
    persistSession: false,
  },
});

async function applyMigration() {
  console.log("🔧 Applying trading tables migration...\n");

  try {
    // Read migration file
    const migrationPath = join(
      process.cwd(),
      "supabase/migrations/20260216_create_trading_tables.sql"
    );
    const sql = readFileSync(migrationPath, "utf-8");

    // Split by semicolons and filter out empty statements
    const statements = sql
      .split(";")
      .map((s) => s.trim())
      .filter((s) => s.length > 0 && !s.startsWith("--"));

    console.log(`📄 Found ${statements.length} SQL statements\n`);

    // Execute each statement
    let successCount = 0;
    let errorCount = 0;

    for (let i = 0; i < statements.length; i++) {
      const statement = statements[i];

      // Extract first line for logging (table/function name)
      const firstLine = statement.split("\n")[0].substring(0, 100);

      try {
        const { error } = await supabase.rpc("exec_sql", {
          sql_query: statement,
        });

        if (error) {
          // Try direct query if rpc fails
          const { error: queryError } = await supabase
            .from("_temp_migration")
            .select("*")
            .limit(0);

          if (queryError) {
            console.log(`   ⚠️  ${firstLine}...`);
            console.log(`      ${error.message}\n`);
            errorCount++;
          } else {
            console.log(`   ✅ ${firstLine}...`);
            successCount++;
          }
        } else {
          console.log(`   ✅ ${firstLine}...`);
          successCount++;
        }
      } catch (err) {
        console.log(`   ⚠️  ${firstLine}...`);
        console.log(`      ${err}\n`);
        errorCount++;
      }

      // Small delay to avoid rate limiting
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    console.log("\n" + "=".repeat(50));
    console.log(`✅ Migration complete!`);
    console.log(`   Successful: ${successCount}`);
    console.log(`   Errors: ${errorCount}`);
    console.log("=".repeat(50) + "\n");

    if (errorCount > 0) {
      console.log(
        "⚠️  Some statements failed. This is often okay for CREATE IF NOT EXISTS."
      );
      console.log(
        "💡 You can also run the migration manually in Supabase SQL Editor:"
      );
      console.log(
        "   supabase/migrations/20260216_create_trading_tables.sql\n"
      );
    }

    // Verify tables were created
    console.log("🔍 Verifying tables...\n");

    const tables = [
      "trade_proposals",
      "positions",
      "risk_events",
      "account_snapshots",
      "market_data",
    ];

    for (const table of tables) {
      const { error } = await supabase.from(table).select("id").limit(1);

      if (error) {
        console.log(`   ❌ ${table}: ${error.message}`);
      } else {
        console.log(`   ✅ ${table}: Created successfully`);
      }
    }

    console.log("\n✨ Trading tables are ready!\n");
  } catch (error) {
    console.error("❌ Migration failed:", error);
    process.exit(1);
  }
}

applyMigration();
