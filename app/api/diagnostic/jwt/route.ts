/**
 * GET /api/diagnostic/jwt - Decode JWT token to verify project ref
 */

import { NextResponse } from "next/server";

export async function GET() {
  try {
    const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;

    if (!serviceRoleKey) {
      return NextResponse.json({
        status: "error",
        error: "SUPABASE_SERVICE_ROLE_KEY not found",
      });
    }

    if (!supabaseUrl) {
      return NextResponse.json({
        status: "error",
        error: "NEXT_PUBLIC_SUPABASE_URL not found",
      });
    }

    // Extract ref from URL
    const urlMatch = supabaseUrl.match(/https:\/\/([^.]+)\.supabase\.co/);
    const urlRef = urlMatch ? urlMatch[1] : "unknown";

    // Decode JWT (just the payload, without verification)
    const parts = serviceRoleKey.split(".");
    if (parts.length !== 3) {
      return NextResponse.json({
        status: "error",
        error: "Invalid JWT format (expected 3 parts)",
      });
    }

    try {
      // Decode base64 payload
      const payload = JSON.parse(
        Buffer.from(parts[1], "base64").toString("utf8")
      );

      return NextResponse.json({
        status: "ok",
        comparison: {
          urlRef: urlRef,
          jwtRef: payload.ref || "not found in JWT",
          match: urlRef === payload.ref,
        },
        jwt: {
          issuer: payload.iss,
          ref: payload.ref,
          role: payload.role,
          issuedAt: payload.iat
            ? new Date(payload.iat * 1000).toISOString()
            : "unknown",
          expiresAt: payload.exp
            ? new Date(payload.exp * 1000).toISOString()
            : "unknown",
          expired: payload.exp ? Date.now() > payload.exp * 1000 : false,
        },
      });
    } catch (decodeError) {
      return NextResponse.json({
        status: "error",
        error: "Failed to decode JWT payload",
        details:
          decodeError instanceof Error ? decodeError.message : String(decodeError),
      });
    }
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
