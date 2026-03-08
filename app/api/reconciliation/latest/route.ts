import { NextResponse } from "next/server";
import { getLatestReconciliation, isPythonBackendEnabled } from "@/lib/trading/python-backend";
import { requireOperatorKey } from "@/app/api/_lib/require-operator-key";

export async function GET(request: Request) {
  const authError = requireOperatorKey(request);
  if (authError) return authError;
  if (!isPythonBackendEnabled()) {
    return NextResponse.json({ error: "Python backend not configured" }, { status: 503 });
  }
  try {
    const data = await getLatestReconciliation();
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 500 });
  }
}
