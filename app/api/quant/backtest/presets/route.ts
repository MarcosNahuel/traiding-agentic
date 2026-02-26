import { NextResponse } from "next/server";
import {
  getBacktestPresets,
  isPythonBackendEnabled,
} from "@/lib/trading/python-backend";

export async function GET() {
  if (!isPythonBackendEnabled()) {
    return NextResponse.json(
      { error: "Python backend not configured" },
      { status: 503 }
    );
  }

  try {
    const presets = await getBacktestPresets();
    return NextResponse.json(presets);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 }
    );
  }
}
