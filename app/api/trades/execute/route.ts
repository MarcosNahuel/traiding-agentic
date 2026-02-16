/**
 * POST /api/trades/execute - Execute approved trade proposals
 *
 * Can execute a specific proposal by ID or all approved proposals
 */

import { NextRequest, NextResponse } from "next/server";
import {
  executeTradeProposal,
  executeApprovedProposals,
} from "@/lib/trading/executor";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { proposalId, executeAll = false } = body;

    // ========================================================================
    // EXECUTE SINGLE PROPOSAL
    // ========================================================================

    if (proposalId && !executeAll) {
      const result = await executeTradeProposal(proposalId);

      if (!result.success) {
        return NextResponse.json(
          {
            success: false,
            error: result.error,
            details: result.details,
          },
          { status: 400 }
        );
      }

      return NextResponse.json({
        success: true,
        message: "Trade executed successfully",
        execution: {
          proposalId,
          orderId: result.orderId,
          executedPrice: result.executedPrice,
          executedQuantity: result.executedQuantity,
          commission: result.commission,
          commissionAsset: result.commissionAsset,
        },
      });
    }

    // ========================================================================
    // EXECUTE ALL APPROVED PROPOSALS
    // ========================================================================

    if (executeAll) {
      const { executed, failed, results } = await executeApprovedProposals();

      return NextResponse.json({
        success: true,
        message: `Executed ${executed} trades, ${failed} failed`,
        summary: {
          executed,
          failed,
          total: executed + failed,
        },
        results: results.map((r, i) => ({
          success: r.success,
          orderId: r.orderId,
          error: r.error,
        })),
      });
    }

    // ========================================================================
    // INVALID REQUEST
    // ========================================================================

    return NextResponse.json(
      {
        error:
          "Either proposalId or executeAll=true must be provided",
      },
      { status: 400 }
    );
  } catch (error) {
    console.error("Error in POST /api/trades/execute:", error);
    return NextResponse.json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
