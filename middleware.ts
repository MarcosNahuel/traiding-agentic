import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/auth/token";

// Rutas públicas que NO requieren autenticación
const PUBLIC_PATHS = [
  "/login",
  "/api/health",
  "/api/auth",
  "/api/telegram",
  "/favicon.ico",
];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some((p) => pathname.startsWith(p));
}

async function getExpectedToken(): Promise<string> {
  const operatorKey = process.env.OPERATOR_API_KEY?.trim();
  if (!operatorKey) return "";
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(operatorKey),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode("session-v1"));
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 32);
}

async function timingSafeEqual(a: string, b: string): Promise<boolean> {
  if (a.length !== b.length) return false;
  const enc = new TextEncoder();
  const [ka, kb] = await Promise.all([
    crypto.subtle.importKey(
      "raw",
      enc.encode(a),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    ),
    crypto.subtle.importKey(
      "raw",
      enc.encode(b),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    ),
  ]);
  const [sa, sb] = await Promise.all([
    crypto.subtle.sign("HMAC", ka, enc.encode("compare")),
    crypto.subtle.sign("HMAC", kb, enc.encode("compare")),
  ]);
  const va = new Uint8Array(sa);
  const vb = new Uint8Array(sb);
  return va.every((byte, i) => byte === vb[i]);
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Si OPERATOR_API_KEY no está configurada, permitir todo (dev sin auth)
  if (!process.env.OPERATOR_API_KEY) {
    return NextResponse.next();
  }

  // Rutas públicas siempre pasan
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  // Verificar cookie de sesión
  const session = request.cookies.get(SESSION_COOKIE);
  const sessionValue = session?.value ?? "";
  const expectedToken = await getExpectedToken();

  const valid = expectedToken && (await timingSafeEqual(sessionValue, expectedToken));

  if (!valid) {
    // API routes → 401 JSON
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    // Páginas → redirect a /login
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
