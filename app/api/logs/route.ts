import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

type LogStatus = "success" | "warning" | "error" | "info" | "pending";

interface ApiLog {
  id: string;
  agent_name: string;
  action: string;
  status: LogStatus;
  created_at: string;
  output_summary: string | null;
}

function parseLimit(raw: string | null): number {
  const value = Number(raw ?? "20");
  if (!Number.isFinite(value)) return 20;
  return Math.min(100, Math.max(1, Math.floor(value)));
}

export async function GET(request: NextRequest) {
  try {
    const supabase = createServerClient();
    const limit = parseLimit(request.nextUrl.searchParams.get("limit"));

    const [riskResult, sourcesResult] = await Promise.all([
      supabase
        .from("risk_events")
        .select("id, event_type, severity, description, created_at, resolved")
        .order("created_at", { ascending: false })
        .limit(limit),
      supabase
        .from("sources")
        .select("id, title, status, updated_at")
        .order("updated_at", { ascending: false })
        .limit(limit),
    ]);

    const riskLogs: ApiLog[] = (riskResult.data ?? []).map((event) => {
      let status: LogStatus = "info";
      if (event.resolved) status = "success";
      else if (event.severity === "critical") status = "error";
      else if (event.severity === "warning") status = "warning";

      return {
        id: `risk-${event.id}`,
        agent_name: "risk-manager",
        action: event.event_type,
        status,
        created_at: event.created_at,
        output_summary: event.description ?? null,
      };
    });

    const sourceLogs: ApiLog[] = (sourcesResult.data ?? []).map((source) => {
      let status: LogStatus = "info";
      if (source.status === "approved") status = "success";
      else if (source.status === "rejected") status = "warning";
      else if (source.status === "error") status = "error";
      else if (source.status === "pending") status = "pending";

      return {
        id: `source-${source.id}`,
        agent_name: "source-agent",
        action: `source_${source.status}`,
        status,
        created_at: source.updated_at,
        output_summary: source.title ?? "Source sin titulo",
      };
    });

    const logs = [...riskLogs, ...sourceLogs]
      .sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      )
      .slice(0, limit);

    return NextResponse.json({
      logs,
      total: logs.length,
      limit,
      offset: 0,
      errors: {
        risk: riskResult.error?.message ?? null,
        sources: sourcesResult.error?.message ?? null,
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        logs: [],
        total: 0,
        limit: 20,
        offset: 0,
        error: "Failed to fetch logs",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
