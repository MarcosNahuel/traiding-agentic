import { NextResponse } from "next/server";
import { getBackendHealth, isPythonBackendEnabled } from "@/lib/trading/python-backend";

export async function GET() {
  const frontendChecks: Record<string, string> = {};

  // Check env vars
  frontendChecks["python_backend"] = isPythonBackendEnabled() ? "ok" : "not_configured";
  frontendChecks["supabase_url"] = process.env.NEXT_PUBLIC_SUPABASE_URL ? "ok" : "missing";
  frontendChecks["supabase_key"] = process.env.SUPABASE_SERVICE_ROLE_KEY ? "ok" : "missing";

  // Proxy to Python backend health
  let backendHealth: any = null;
  if (isPythonBackendEnabled()) {
    try {
      backendHealth = await getBackendHealth();
    } catch (e) {
      backendHealth = { status: "unreachable", error: e instanceof Error ? e.message : String(e) };
    }
  }

  const frontendOk = Object.values(frontendChecks).every((v) => v === "ok" || v === "not_configured");
  const backendOk = backendHealth?.status === "healthy";

  let overall = "healthy";
  if (!frontendOk || backendHealth?.status === "unhealthy") {
    overall = "unhealthy";
  } else if (!backendOk) {
    overall = "degraded";
  }

  return NextResponse.json({
    status: overall,
    frontend: { checks: frontendChecks },
    backend: backendHealth,
    timestamp: new Date().toISOString(),
  });
}
