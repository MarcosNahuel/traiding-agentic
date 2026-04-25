import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { validateApprovalToken } from "../_lib/token-validator";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const token = url.searchParams.get("token");
  const id = url.searchParams.get("id");

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

  // Fetch the pending config
  const { data: pending, error: fetchErr } = await supabase
    .from("llm_trading_configs")
    .select("id, status")
    .eq("id", id)
    .single();

  if (fetchErr || !pending) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }

  if (pending.status === "active") {
    return NextResponse.json({ ok: true, message: "already_active" });
  }
  if (pending.status === "rejected" || pending.status === "expired") {
    return NextResponse.json(
      { error: "already_processed", current_status: pending.status },
      { status: 409 },
    );
  }
  if (pending.status !== "pending_approval") {
    return NextResponse.json(
      { error: "invalid_state", current_status: pending.status },
      { status: 409 },
    );
  }

  const now = new Date().toISOString();

  // Supersede any other active configs first
  await supabase
    .from("llm_trading_configs")
    .update({ status: "superseded", superseded_at: now })
    .eq("status", "active");

  // Promote to active
  const { error: updateErr } = await supabase
    .from("llm_trading_configs")
    .update({
      status: "active",
      approved_at: now,
      approved_by: "telegram_inline_button",
    })
    .eq("id", id);

  if (updateErr) {
    return NextResponse.json({ error: "update_failed", detail: updateErr.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true, message: "approved", id });
}
