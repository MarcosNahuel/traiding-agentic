import { NextResponse } from "next/server";
import { getPerformanceMetrics, isPythonBackendEnabled } from "@/lib/trading/python-backend";

export async function GET() {
  if (!isPythonBackendEnabled()) {
    return NextResponse.json(
      { error: "Python backend not configured" },
      { status: 503 }
    );
  }
  try {
    const metrics = await getPerformanceMetrics();
    return NextResponse.json(metrics);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 }
    );
  }
}
