/**
 * GET /api/trades/proposals/[id] - Get specific proposal
 * PATCH /api/trades/proposals/[id] - Approve/reject proposal
 * DELETE /api/trades/proposals/[id] - Cancel proposal
 */

import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";
import { logRiskEvent } from "@/lib/trading/risk-manager";

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const supabase = createServerClient();

    const { data: proposal, error } = await supabase
      .from("trade_proposals")
      .select("*, strategies_found(name, description)")
      .eq("id", params.id)
      .single();

    if (error || !proposal) {
      return NextResponse.json(
        { error: "Proposal not found" },
        { status: 404 }
      );
    }

    return NextResponse.json({ proposal });
  } catch (error) {
    console.error("Error in GET /api/trades/proposals/[id]:", error);
    return NextResponse.json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await req.json();
    const { action, notes } = body; // action: 'approve' | 'reject'

    if (!action || !["approve", "reject"].includes(action)) {
      return NextResponse.json(
        { error: "action must be 'approve' or 'reject'" },
        { status: 400 }
      );
    }

    const supabase = createServerClient();

    // Get current proposal
    const { data: proposal, error: fetchError } = await supabase
      .from("trade_proposals")
      .select("*")
      .eq("id", params.id)
      .single();

    if (fetchError || !proposal) {
      return NextResponse.json(
        { error: "Proposal not found" },
        { status: 404 }
      );
    }

    // ========================================================================
    // VALIDATE STATE TRANSITION
    // ========================================================================

    const currentStatus = proposal.status;

    // Can only approve/reject validated proposals
    if (currentStatus !== "validated") {
      return NextResponse.json(
        {
          error: `Cannot ${action} proposal in status '${currentStatus}'. Only 'validated' proposals can be approved/rejected.`,
        },
        { status: 400 }
      );
    }

    // ========================================================================
    // UPDATE PROPOSAL STATUS
    // ========================================================================

    const newStatus = action === "approve" ? "approved" : "rejected";
    const timestamp = new Date().toISOString();

    const updateData: any = {
      status: newStatus,
      updated_at: timestamp,
    };

    if (action === "approve") {
      updateData.approved_at = timestamp;
    } else {
      updateData.rejected_at = timestamp;
      if (notes) {
        updateData.error_message = notes;
      }
    }

    const { data: updatedProposal, error: updateError } = await supabase
      .from("trade_proposals")
      .update(updateData)
      .eq("id", params.id)
      .select()
      .single();

    if (updateError) {
      return NextResponse.json(
        {
          error: "Failed to update proposal",
          details: updateError.message,
        },
        { status: 500 }
      );
    }

    // ========================================================================
    // LOG EVENT
    // ========================================================================

    await logRiskEvent(
      `proposal_${action}d`,
      action === "approve" ? "info" : "warning",
      `Trade proposal ${action}d by user`,
      {
        proposalId: params.id,
        symbol: proposal.symbol,
        notional: proposal.notional,
        notes,
      },
      undefined,
      params.id
    );

    // ========================================================================
    // RETURN RESPONSE
    // ========================================================================

    return NextResponse.json({
      success: true,
      proposalId: params.id,
      status: newStatus,
      message: `Proposal ${action}d successfully`,
      proposal: updatedProposal,
    });
  } catch (error) {
    console.error("Error in PATCH /api/trades/proposals/[id]:", error);
    return NextResponse.json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const supabase = createServerClient();

    // Get current proposal
    const { data: proposal, error: fetchError } = await supabase
      .from("trade_proposals")
      .select("*")
      .eq("id", params.id)
      .single();

    if (fetchError || !proposal) {
      return NextResponse.json(
        { error: "Proposal not found" },
        { status: 404 }
      );
    }

    // Can only cancel proposals that haven't been executed
    if (proposal.status === "executed") {
      return NextResponse.json(
        { error: "Cannot cancel executed proposal" },
        { status: 400 }
      );
    }

    // Soft delete by updating status to 'rejected'
    const { error: updateError } = await supabase
      .from("trade_proposals")
      .update({
        status: "rejected",
        error_message: "Cancelled by user",
        rejected_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq("id", params.id);

    if (updateError) {
      return NextResponse.json(
        {
          error: "Failed to cancel proposal",
          details: updateError.message,
        },
        { status: 500 }
      );
    }

    await logRiskEvent(
      "proposal_cancelled",
      "info",
      "Trade proposal cancelled by user",
      {
        proposalId: params.id,
        symbol: proposal.symbol,
      },
      undefined,
      params.id
    );

    return NextResponse.json({
      success: true,
      message: "Proposal cancelled successfully",
    });
  } catch (error) {
    console.error("Error in DELETE /api/trades/proposals/[id]:", error);
    return NextResponse.json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
