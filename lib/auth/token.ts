/**
 * Shared token utility — importable desde server components y api routes (Node.js).
 * El middleware Edge usa crypto.subtle directamente (ver middleware.ts).
 */
import { createHmac } from "crypto";

export { SESSION_COOKIE } from "./constants";

export function getSessionToken(): string {
  const operatorKey = process.env.OPERATOR_API_KEY?.trim();
  if (!operatorKey) return "";
  // HMAC-SHA256 — no reversible, no expone OPERATOR_API_KEY
  return createHmac("sha256", operatorKey)
    .update("session-v1")
    .digest("hex")
    .slice(0, 32);
}
