import { NextRequest, NextResponse } from "next/server";
import { isPythonBackendEnabled, executeProposal } from "@/lib/trading/python-backend";
import { executeTradeProposal, executeApprovedProposals } from "@/lib/trading/executor";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { proposalId, executeAll } = body;

    if (isPythonBackendEnabled()) {
      const result = await executeProposal({
        proposal_id: proposalId,
        execute_all: executeAll || false,
      });
      return NextResponse.json(result);
    }

    // Fallback: original Next.js logic
    if (executeAll) {
      const result = await executeApprovedProposals();
      return NextResponse.json({
        success: true,
        message: `Executed ${result.executed}/${result.executed + result.failed} proposals`,
        summary: result,
      });
    }
    if (proposalId) {
      const result = await executeTradeProposal(proposalId);
      if (!result.success) return NextResponse.json({ error: result.error }, { status: 400 });
      return NextResponse.json({ success: true, message: "Trade executed successfully", execution: result });
    }
    return NextResponse.json({ error: "Provide proposalId or executeAll=true" }, { status: 400 });
  } catch (e: unknown) {
    console.error("POST /api/trades/execute error:", e);
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
