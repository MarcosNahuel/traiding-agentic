/**
 * GET /api/diagnostic - Check environment variables (without exposing values)
 */

import { NextResponse } from "next/server";

export async function GET() {
  try {
    const envCheck = {
      timestamp: new Date().toISOString(),
      nodeEnv: process.env.NODE_ENV,
      variables: {
        NEXT_PUBLIC_SUPABASE_URL: {
          exists: !!process.env.NEXT_PUBLIC_SUPABASE_URL,
          length: process.env.NEXT_PUBLIC_SUPABASE_URL?.length || 0,
          prefix: process.env.NEXT_PUBLIC_SUPABASE_URL?.substring(0, 8) || "N/A",
        },
        SUPABASE_SERVICE_ROLE_KEY: {
          exists: !!process.env.SUPABASE_SERVICE_ROLE_KEY,
          length: process.env.SUPABASE_SERVICE_ROLE_KEY?.length || 0,
          prefix: process.env.SUPABASE_SERVICE_ROLE_KEY?.substring(0, 6) || "N/A",
        },
        GOOGLE_AI_API_KEY: {
          exists: !!process.env.GOOGLE_AI_API_KEY,
          length: process.env.GOOGLE_AI_API_KEY?.length || 0,
          prefix: process.env.GOOGLE_AI_API_KEY?.substring(0, 6) || "N/A",
        },
        TELEGRAM_BOT_TOKEN: {
          exists: !!process.env.TELEGRAM_BOT_TOKEN,
          length: process.env.TELEGRAM_BOT_TOKEN?.length || 0,
        },
        NEXT_PUBLIC_APP_URL: {
          exists: !!process.env.NEXT_PUBLIC_APP_URL,
          value: process.env.NEXT_PUBLIC_APP_URL, // Safe to expose
        },
      },
    };

    return NextResponse.json({
      status: "ok",
      ...envCheck,
    });
  } catch (error) {
    return NextResponse.json(
      {
        status: "error",
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
