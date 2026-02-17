import { NextRequest, NextResponse } from "next/server";
import { isPythonBackendEnabled, getProposal, updateProposal } from "@/lib/trading/python-backend";
import { createServerClient } from "@/lib/supabase";
import { logRiskEvent } from "@/lib/trading/risk-manager";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    if (isPythonBackendEnabled()) {
      return NextResponse.json(await getProposal(id));
    }
    const supabase = createServerClient();
    const { data, error } = await supabase.from("trade_proposals").select("*").eq("id", id).single();
    if (error || !data) return NextResponse.json({ error: "Not found" }, { status: 404 });
    return NextResponse.json({ proposal: data });
  } catch (e: unknown) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const body = await request.json();

    if (isPythonBackendEnabled()) {
      return NextResponse.json(await updateProposal(id, { action: body.action, notes: body.notes }));
    }

    // Fallback
    const supabase = createServerClient();
    const { data: proposal } = await supabase.from("trade_proposals").select("*").eq("id", id).single();
    if (!proposal) return NextResponse.json({ error: "Not found" }, { status: 404 });
    if (proposal.status !== "validated") {
      return NextResponse.json({ error: `Cannot ${body.action} proposal in '${proposal.status}' status` }, { status: 400 });
    }

    const now = new Date().toISOString();
    const newStatus = body.action === "approve" ? "approved" : "rejected";
    await supabase.from("trade_proposals").update({
      status: newStatus,
      ...(newStatus === "approved" ? { approved_at: now } : { rejected_at: now }),
      updated_at: now,
    }).eq("id", id);

    await logRiskEvent(
      newStatus === "approved" ? "proposal_approved" : "proposal_rejected",
      newStatus === "approved" ? "info" : "warning",
      `Trade proposal ${newStatus} by user`,
      { notes: body.notes }, undefined, id
    );

    const { data: final } = await supabase.from("trade_proposals").select("*").eq("id", id).single();
    return NextResponse.json({ success: true, proposalId: id, status: newStatus, proposal: final });
  } catch (e: unknown) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const supabase = createServerClient();
    const { data: proposal } = await supabase.from("trade_proposals").select("status").eq("id", id).single();
    if (!proposal) return NextResponse.json({ error: "Not found" }, { status: 404 });
    if (proposal.status === "executed") return NextResponse.json({ error: "Cannot cancel executed proposal" }, { status: 400 });
    const now = new Date().toISOString();
    await supabase.from("trade_proposals").update({ status: "rejected", rejected_at: now, updated_at: now }).eq("id", id);
    return NextResponse.json({ success: true, message: "Proposal cancelled" });
  } catch (e: unknown) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
