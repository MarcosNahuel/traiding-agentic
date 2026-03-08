import { NextResponse } from "next/server";
import { timingSafeEqual } from "crypto";

function safeCompare(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  return timingSafeEqual(Buffer.from(a), Buffer.from(b));
}

export function requireApiKey(
  request: Request,
  envVar: string,
  headerName: string,
  disabledMessage: string
): NextResponse | null {
  const apiKey = process.env[envVar];
  if (!apiKey) {
    if (process.env.NODE_ENV === "production") {
      return NextResponse.json({ error: disabledMessage }, { status: 403 });
    }
    return null;
  }
  const providedKey = request.headers.get(headerName);
  if (!providedKey || !safeCompare(providedKey, apiKey)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return null;
}
