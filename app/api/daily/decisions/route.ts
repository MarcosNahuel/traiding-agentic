import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const days = parseInt(searchParams.get("days") || "14", 10);

  try {
    const supabase = createServerClient();

    // Fetch audit reports (post-market analysis)
    const { data: audits, error: auditErr } = await supabase
      .from("llm_audit_reports")
      .select("*")
      .order("audit_date", { ascending: false })
      .limit(days);

    if (auditErr) throw auditErr;

    // Fetch config decisions (pre-market config changes)
    const { data: configs, error: configErr } = await supabase
      .from("llm_trading_configs")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(days * 2);

    if (configErr) throw configErr;

    // Fetch daily briefs if table exists
    let briefs: Record<string, unknown>[] = [];
    try {
      const { data } = await supabase
        .from("llm_daily_briefs")
        .select("*")
        .order("brief_date", { ascending: false })
        .limit(days);
      briefs = data || [];
    } catch {
      // Table may not exist
    }

    // Merge by date
    const dateMap: Record<string, {
      date: string;
      audit: Record<string, unknown> | null;
      config: Record<string, unknown> | null;
      brief: Record<string, unknown> | null;
    }> = {};

    for (const a of audits || []) {
      const d = a.audit_date;
      if (!dateMap[d]) dateMap[d] = { date: d, audit: null, config: null, brief: null };
      dateMap[d].audit = a;
    }

    for (const c of configs || []) {
      const d = (c.created_at as string).slice(0, 10);
      if (!dateMap[d]) dateMap[d] = { date: d, audit: null, config: null, brief: null };
      if (!dateMap[d].config) dateMap[d].config = c;
    }

    for (const b of briefs) {
      const d = b.brief_date as string;
      if (!dateMap[d]) dateMap[d] = { date: d, audit: null, config: null, brief: null };
      dateMap[d].brief = b;
    }

    const decisions = Object.values(dateMap).sort(
      (a, b) => b.date.localeCompare(a.date)
    );

    return NextResponse.json({ decisions, total: decisions.length });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 }
    );
  }
}
