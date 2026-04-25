import { timingSafeEqual } from "node:crypto";

/**
 * Timing-safe comparison of approval token from query string vs env var.
 * Returns false on any error (missing env, length mismatch, etc).
 */
export function validateApprovalToken(provided: string | null): boolean {
  if (!provided) return false;
  const expected = process.env.STRATEGIST_APPROVAL_TOKEN;
  if (!expected) {
    console.error("STRATEGIST_APPROVAL_TOKEN not set");
    return false;
  }
  if (provided.length !== expected.length) return false;
  try {
    return timingSafeEqual(
      Buffer.from(provided, "utf8"),
      Buffer.from(expected, "utf8"),
    );
  } catch {
    return false;
  }
}
