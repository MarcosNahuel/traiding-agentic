/**
 * GET /api/diagnostic/supabase - Test Supabase connection
 */

import { NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET() {
  const diagnostics: any = {
    timestamp: new Date().toISOString(),
    steps: [],
  };

  try {
    // Step 1: Check environment variables
    diagnostics.steps.push({
      step: "check_env_vars",
      status: "success",
      supabaseUrlExists: !!process.env.NEXT_PUBLIC_SUPABASE_URL,
      serviceRoleKeyExists: !!process.env.SUPABASE_SERVICE_ROLE_KEY,
    });

    // Step 2: Try to create Supabase client
    let supabase;
    try {
      supabase = createServerClient();
      diagnostics.steps.push({
        step: "create_client",
        status: "success",
      });
    } catch (error) {
      diagnostics.steps.push({
        step: "create_client",
        status: "error",
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }

    // Step 3: Try a simple query
    try {
      const { data, error } = await supabase
        .from("sources")
        .select("id")
        .limit(1);

      if (error) {
        diagnostics.steps.push({
          step: "query_sources",
          status: "error",
          supabaseError: {
            message: error.message,
            details: error.details,
            hint: error.hint,
            code: error.code,
          },
        });
      } else {
        diagnostics.steps.push({
          step: "query_sources",
          status: "success",
          recordsFound: data?.length || 0,
        });
      }
    } catch (error) {
      diagnostics.steps.push({
        step: "query_sources",
        status: "error",
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }

    // Step 4: Try to check other tables
    try {
      const { error: strategiesError } = await supabase
        .from("strategies_found")
        .select("id")
        .limit(1);

      diagnostics.steps.push({
        step: "query_strategies",
        status: strategiesError ? "error" : "success",
        error: strategiesError?.message,
      });
    } catch (error) {
      diagnostics.steps.push({
        step: "query_strategies",
        status: "error",
        error: error instanceof Error ? error.message : String(error),
      });
    }

    return NextResponse.json({
      status: "ok",
      ...diagnostics,
    });
  } catch (error) {
    return NextResponse.json(
      {
        status: "error",
        error: error instanceof Error ? error.message : String(error),
        ...diagnostics,
      },
      { status: 500 }
    );
  }
}
