import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { validateApprovalToken } from "../_lib/token-validator";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const token = url.searchParams.get("token");
  const id = url.searchParams.get("id");
  const reason = url.searchParams.get("reason") || "manual_reject";

  if (!validateApprovalToken(token)) {
    return NextResponse.json({ error: "invalid_token" }, { status: 401 });
  }
  if (!id) {
    return NextResponse.json({ error: "missing_id" }, { status: 400 });
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!supabaseUrl || !supabaseKey) {
    return NextResponse.json({ error: "server_misconfigured" }, { status: 500 });
  }
  const supabase = createClient(supabaseUrl, supabaseKey);

  const { data: pending } = await supabase
    .from("llm_trading_configs")
    .select("id, status")
    .eq("id", id)
    .single();

  if (!pending) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
  if (pending.status === "rejected") {
    return NextResponse.json({ ok: true, message: "already_rejected" });
  }
  if (pending.status !== "pending_approval") {
    return NextResponse.json(
      { error: "invalid_state", current_status: pending.status },
      { status: 409 },
    );
  }

  const { error } = await supabase
    .from("llm_trading_configs")
    .update({
      status: "rejected",
      rejection_reason: reason.slice(0, 500),
    })
    .eq("id", id);

  if (error) {
    return NextResponse.json({ error: "update_failed" }, { status: 500 });
  }
  return NextResponse.json({ ok: true, message: "rejected", id });
}
