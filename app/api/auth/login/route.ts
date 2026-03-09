import { NextRequest, NextResponse } from "next/server";
import { setSessionCookie, getSessionToken } from "@/lib/auth/session";

export async function POST(request: NextRequest) {
  let password: string | undefined;
  try {
    const body = await request.json();
    password = typeof body?.password === "string" ? body.password : undefined;
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 });
  }
  const operatorKey = process.env.OPERATOR_API_KEY;

  if (!operatorKey) {
    // Sin OPERATOR_API_KEY configurada: aceptar cualquier password en dev
    if (process.env.NODE_ENV !== "production") {
      const response = NextResponse.json({ success: true });
      return setSessionCookie(response);
    }
    return NextResponse.json({ error: "Auth not configured" }, { status: 503 });
  }

  if (password !== operatorKey) {
    return NextResponse.json({ error: "Invalid password" }, { status: 401 });
  }

  const response = NextResponse.json({ success: true });
  return setSessionCookie(response);
}
