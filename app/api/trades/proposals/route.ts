/**
 * POST /api/trades/proposals - Create a new trade proposal
 * GET /api/trades/proposals - List trade proposals with filtering
 */

import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";
import {
  validateTradeProposal,
  DEFAULT_RISK_LIMITS,
  logRiskEvent,
} from "@/lib/trading/risk-manager";
import { getPrice } from "@/lib/exchanges/binance-testnet";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const {
      type,
      symbol,
      quantity,
      price, // Optional for market orders
      orderType = "MARKET",
      strategyId,
      reasoning,
    } = body;

    // ========================================================================
    // INPUT VALIDATION
    // ========================================================================

    if (!type || !["buy", "sell"].includes(type)) {
      return NextResponse.json(
        { error: "type must be 'buy' or 'sell'" },
        { status: 400 }
      );
    }

    if (!symbol || typeof symbol !== "string") {
      return NextResponse.json(
        { error: "symbol is required (e.g., 'BTCUSDT')" },
        { status: 400 }
      );
    }

    if (!quantity || quantity <= 0) {
      return NextResponse.json(
        { error: "quantity must be a positive number" },
        { status: 400 }
      );
    }

    if (!["MARKET", "LIMIT"].includes(orderType)) {
      return NextResponse.json(
        { error: "orderType must be 'MARKET' or 'LIMIT'" },
        { status: 400 }
      );
    }

    if (orderType === "LIMIT" && (!price || price <= 0)) {
      return NextResponse.json(
        { error: "price is required for LIMIT orders" },
        { status: 400 }
      );
    }

    // ========================================================================
    // CALCULATE NOTIONAL VALUE
    // ========================================================================

    let estimatedPrice: number;

    if (orderType === "LIMIT" && price) {
      estimatedPrice = price;
    } else {
      // For market orders, get current price
      try {
        const priceData = await getPrice(symbol);
        estimatedPrice = parseFloat(priceData.price);
      } catch (error) {
        return NextResponse.json(
          {
            error: "Failed to fetch current price",
            details: error instanceof Error ? error.message : String(error),
          },
          { status: 500 }
        );
      }
    }

    const notional = quantity * estimatedPrice;

    // ========================================================================
    // CREATE PROPOSAL IN DB (status: draft)
    // ========================================================================

    const supabase = createServerClient();

    const { data: proposal, error: insertError } = await supabase
      .from("trade_proposals")
      .insert({
        type,
        symbol,
        quantity,
        price: orderType === "LIMIT" ? price : estimatedPrice,
        order_type: orderType,
        notional,
        status: "draft",
        strategy_id: strategyId,
        reasoning,
      })
      .select()
      .single();

    if (insertError || !proposal) {
      return NextResponse.json(
        {
          error: "Failed to create proposal",
          details: insertError?.message,
        },
        { status: 500 }
      );
    }

    // ========================================================================
    // VALIDATE WITH RISK MANAGER
    // ========================================================================

    const validationResult = await validateTradeProposal(
      {
        id: proposal.id,
        type,
        symbol,
        quantity,
        price: estimatedPrice,
        orderType,
        notional,
        strategyId,
        reasoning,
      },
      DEFAULT_RISK_LIMITS
    );

    // ========================================================================
    // UPDATE PROPOSAL WITH VALIDATION RESULTS
    // ========================================================================

    const newStatus = validationResult.approved ? "validated" : "rejected";
    const autoApproved =
      validationResult.approved && validationResult.autoApproved;

    const updateData: any = {
      status: autoApproved ? "approved" : newStatus,
      risk_score: validationResult.riskScore,
      risk_checks: validationResult.checks,
      auto_approved: autoApproved,
      validated_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    if (autoApproved) {
      updateData.approved_at = new Date().toISOString();
    }

    if (!validationResult.approved && validationResult.rejectionReason) {
      updateData.error_message = validationResult.rejectionReason;
    }

    const { data: updatedProposal, error: updateError } = await supabase
      .from("trade_proposals")
      .update(updateData)
      .eq("id", proposal.id)
      .select()
      .single();

    if (updateError) {
      console.error("Failed to update proposal:", updateError);
    }

    // ========================================================================
    // LOG RISK EVENTS
    // ========================================================================

    if (!validationResult.approved) {
      await logRiskEvent(
        "proposal_rejected",
        "warning",
        validationResult.rejectionReason || "Proposal failed risk validation",
        {
          proposalId: proposal.id,
          symbol,
          notional,
          checks: validationResult.checks,
        },
        undefined,
        proposal.id
      );
    }

    // Log critical risk checks even if approved
    const criticalWarnings = validationResult.checks.filter(
      (check) => check.severity === "warning" && check.passed
    );

    for (const warning of criticalWarnings) {
      await logRiskEvent(
        "risk_warning",
        "warning",
        warning.message,
        {
          proposalId: proposal.id,
          check: warning.name,
        },
        undefined,
        proposal.id
      );
    }

    // ========================================================================
    // RETURN RESPONSE
    // ========================================================================

    return NextResponse.json({
      success: validationResult.approved,
      proposalId: proposal.id,
      status: autoApproved ? "approved" : newStatus,
      autoApproved,
      riskScore: validationResult.riskScore,
      notional: notional.toFixed(2),
      estimatedPrice: estimatedPrice.toFixed(2),
      validation: {
        approved: validationResult.approved,
        checks: validationResult.checks,
        rejectionReason: validationResult.rejectionReason,
      },
      message: autoApproved
        ? `Trade auto-approved and ready for execution (notional: $${notional.toFixed(2)})`
        : validationResult.approved
          ? `Trade validated successfully. Requires manual approval (notional: $${notional.toFixed(2)})`
          : `Trade rejected: ${validationResult.rejectionReason}`,
      proposal: updatedProposal || proposal,
    });
  } catch (error) {
    console.error("Error in POST /api/trades/proposals:", error);
    return NextResponse.json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);

    // Query parameters
    const status = searchParams.get("status");
    const symbol = searchParams.get("symbol");
    const type = searchParams.get("type");
    const limit = parseInt(searchParams.get("limit") || "50");
    const offset = parseInt(searchParams.get("offset") || "0");

    const supabase = createServerClient();

    // Build query
    let query = supabase
      .from("trade_proposals")
      .select("*, strategies_found(name, description)", { count: "exact" })
      .order("created_at", { ascending: false })
      .range(offset, offset + limit - 1);

    // Apply filters
    if (status) {
      query = query.eq("status", status);
    }

    if (symbol) {
      query = query.eq("symbol", symbol);
    }

    if (type) {
      query = query.eq("type", type);
    }

    const { data, error, count } = await query;

    if (error) {
      return NextResponse.json(
        { error: "Failed to fetch proposals", details: error.message },
        { status: 500 }
      );
    }

    // ========================================================================
    // CALCULATE SUMMARY STATS
    // ========================================================================

    const { data: stats } = await supabase.rpc("get_proposal_stats");

    return NextResponse.json({
      proposals: data || [],
      total: count || 0,
      limit,
      offset,
      stats: stats || {
        pending: 0,
        approved: 0,
        rejected: 0,
        executed: 0,
      },
    });
  } catch (error) {
    console.error("Error in GET /api/trades/proposals:", error);
    return NextResponse.json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
