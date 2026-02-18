import { NextResponse } from "next/server";
import { retryDeadLetter, isPythonBackendEnabled } from "@/lib/trading/python-backend";

export async function POST(_req: Request, { params }: { params: Promise<{ id: string }> }) {
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
