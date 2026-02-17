import { NextResponse } from "next/server";
import { getQuantStatus, isPythonBackendEnabled } from "@/lib/trading/python-backend";

export async function GET() {
  if (!isPythonBackendEnabled()) {
    return NextResponse.json(
      { error: "Python backend not configured", enabled: false },
      { status: 503 }
    );
  }
  try {
    const status = await getQuantStatus();
    return NextResponse.json(status);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 }
    );
  }
}
