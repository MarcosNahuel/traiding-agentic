import { NextRequest, NextResponse } from "next/server";
import { isPythonBackendEnabled, createProposal, listProposals } from "@/lib/trading/python-backend";

// Fallback: original Next.js implementation
import { createServerClient } from "@/lib/supabase";
import { validateTradeProposal, logRiskEvent } from "@/lib/trading/risk-manager";
import { getPrice } from "@/lib/exchanges/binance-client";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { type, symbol, quantity, price, orderType, order_type, strategyId, strategy_id, reasoning } = body;

    if (!type || !symbol || !quantity) {
      return NextResponse.json({ error: "Missing required fields: type, symbol, quantity" }, { status: 400 });
    }

    // --- Python backend path ---
    if (isPythonBackendEnabled()) {
      const result = await createProposal({
        type, symbol, quantity,
        price,
        order_type: orderType || order_type || "MARKET",
        strategy_id: strategyId || strategy_id,
        reasoning,
      });
      return NextResponse.json(result);
    }

    // --- Fallback: original Next.js logic ---
    const supabase = createServerClient();
    const priceData = await getPrice(symbol);
    const currentPrice = parseFloat(priceData.price);
    const effectivePrice = price || currentPrice;
    const notional = quantity * effectivePrice;
    const now = new Date().toISOString();

    const { data: proposal, error } = await supabase
      .from("trade_proposals")
      .insert({
        type, symbol, quantity,
        price: effectivePrice,
        order_type: orderType || order_type || "MARKET",
        notional,
        status: "draft",
        strategy_id: strategyId || strategy_id,
        reasoning,
        risk_score: 0,
        risk_checks: [],
        auto_approved: false,
        retry_count: 0,
      })
      .select()
      .single();

    if (error) throw error;

    const validation = await validateTradeProposal(proposal);
    const newStatus = validation.approved ? (validation.autoApproved ? "approved" : "validated") : "rejected";

    await supabase.from("trade_proposals").update({
      status: newStatus,
      risk_score: validation.riskScore,
      risk_checks: validation.checks,
      auto_approved: validation.autoApproved,
      validated_at: now,
      ...(newStatus === "rejected" ? { rejected_at: now } : {}),
      ...(newStatus === "approved" ? { approved_at: now } : {}),
    }).eq("id", proposal.id);

    await logRiskEvent(
      validation.approved ? "proposal_approved" : "proposal_rejected",
      validation.approved ? "info" : "warning",
      validation.rejectionReason || `Trade proposal validated: ${type.toUpperCase()} ${quantity} ${symbol}`,
      { notional, riskScore: validation.riskScore },
      undefined,
      proposal.id
    );

    const { data: final } = await supabase.from("trade_proposals").select("*").eq("id", proposal.id).single();
    return NextResponse.json({
      success: true, proposalId: proposal.id, status: newStatus,
      autoApproved: validation.autoApproved, riskScore: validation.riskScore,
      notional: `$${notional.toFixed(2)}`, estimatedPrice: `$${effectivePrice.toFixed(2)}`,
      validation: { approved: validation.approved, checks: validation.checks, rejectionReason: validation.rejectionReason },
      proposal: final,
    });
  } catch (error: unknown) {
    console.error("POST /api/trades/proposals error:", error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const params: Record<string, string> = {};
    ["status", "symbol", "type", "limit", "offset"].forEach(k => {
      const v = searchParams.get(k);
      if (v) params[k] = v;
    });

    if (isPythonBackendEnabled()) {
      const result = await listProposals(params);
      return NextResponse.json(result);
    }

    // Fallback
    const supabase = createServerClient();
    let query = supabase.from("trade_proposals").select("*", { count: "exact" });
    if (params.status) query = query.eq("status", params.status);
    if (params.symbol) query = query.eq("symbol", params.symbol);
    if (params.type) query = query.eq("type", params.type);
    const limit = parseInt(params.limit || "50");
    const offset = parseInt(params.offset || "0");
    const { data, count } = await query.order("created_at", { ascending: false }).range(offset, offset + limit - 1);

    return NextResponse.json({ proposals: data || [], total: count || 0, limit, offset, stats: {} });
  } catch (error: unknown) {
    console.error("GET /api/trades/proposals error:", error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
