import { NextResponse } from "next/server";
import { getQuantAnalysis, isPythonBackendEnabled } from "@/lib/trading/python-backend";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ symbol: string }> }
) {
  if (!isPythonBackendEnabled()) {
    return NextResponse.json(
      { error: "Python backend not configured" },
      { status: 503 }
    );
  }
  const { symbol } = await params;
  const { searchParams } = new URL(req.url);
  const interval = searchParams.get("interval") ?? "1h";
  try {
    const analysis = await getQuantAnalysis(symbol.toUpperCase(), interval);
    return NextResponse.json(analysis);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 }
    );
  }
}
