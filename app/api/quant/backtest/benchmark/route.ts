import { NextResponse } from "next/server";
import {
  isPythonBackendEnabled,
  runBacktestBenchmark,
} from "@/lib/trading/python-backend";

export async function POST(req: Request) {
  if (!isPythonBackendEnabled()) {
    return NextResponse.json(
      { error: "Python backend not configured" },
      { status: 503 }
    );
  }

  try {
    const body = await req.json();
    const result = await runBacktestBenchmark(body);
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 }
    );
  }
}
