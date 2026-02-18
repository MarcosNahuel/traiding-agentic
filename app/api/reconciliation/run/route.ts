import { NextResponse } from "next/server";
import { triggerReconciliation, isPythonBackendEnabled } from "@/lib/trading/python-backend";

export async function POST() {
  if (!isPythonBackendEnabled()) {
    return NextResponse.json({ error: "Python backend not configured" }, { status: 503 });
  }
  try {
    const data = await triggerReconciliation();
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 500 });
  }
}
