import { NextResponse } from "next/server";
import { retryDeadLetter, isPythonBackendEnabled } from "@/lib/trading/python-backend";
import { requireOperatorKey } from "@/app/api/_lib/require-operator-key";

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const authError = requireOperatorKey(req);
  if (authError) return authError;
  if (!isPythonBackendEnabled()) {
    return NextResponse.json({ error: "Python backend not configured" }, { status: 503 });
  }
  try {
    const { id } = await params;
    const data = await retryDeadLetter(id);
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 500 });
  }
}
