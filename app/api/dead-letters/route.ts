import { NextResponse } from "next/server";
import { listDeadLetters, isPythonBackendEnabled } from "@/lib/trading/python-backend";

export async function GET() {
  if (!isPythonBackendEnabled()) {
    return NextResponse.json({ error: "Python backend not configured" }, { status: 503 });
  }
  try {
    const data = await listDeadLetters();
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 500 });
  }
}
