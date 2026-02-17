import { NextResponse } from "next/server";
import {
  runBacktest,
  getBacktestResults,
  isPythonBackendEnabled,
} from "@/lib/trading/python-backend";

export async function GET(req: Request) {
  if (!isPythonBackendEnabled()) {
    return NextResponse.json(
      { error: "Python backend not configured" },
      { status: 503 }
    );
  }
  const { searchParams } = new URL(req.url);
  const strategyId = searchParams.get("strategy_id") ?? undefined;
  try {
    const results = await getBacktestResults(strategyId);
    return NextResponse.json(results);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 }
    );
  }
}

export async function POST(req: Request) {
  if (!isPythonBackendEnabled()) {
    return NextResponse.json(
      { error: "Python backend not configured" },
      { status: 503 }
    );
  }
  try {
    const body = await req.json();
    const result = await runBacktest(body);
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 }
    );
  }
}
