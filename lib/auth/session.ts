import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { timingSafeEqual as cryptoTimingSafe } from "crypto";
import { getSessionToken, SESSION_COOKIE } from "./token";

export { getSessionToken, SESSION_COOKIE };

const SESSION_MAX_AGE = 60 * 60 * 24; // 24h

function timingSafeStringEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  return cryptoTimingSafe(Buffer.from(a), Buffer.from(b));
}

export async function isAuthenticated(): Promise<boolean> {
  const cookieStore = await cookies();
  const session = cookieStore.get(SESSION_COOKIE);
  if (!session?.value) return false;
  const expected = getSessionToken();
  if (!expected) return false;
  return timingSafeStringEqual(session.value, expected);
}

export function setSessionCookie(response: NextResponse): NextResponse {
  response.cookies.set(SESSION_COOKIE, getSessionToken(), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: SESSION_MAX_AGE,
    path: "/",
  });
  return response;
}

export function clearSessionCookie(response: NextResponse): NextResponse {
  response.cookies.delete(SESSION_COOKIE);
  return response;
}
