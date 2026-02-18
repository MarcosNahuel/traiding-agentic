/**
 * Trade Executor - Executes approved trade proposals on Binance Testnet
 *
 * This module handles the actual execution of trades that have been
 * approved by the risk manager and/or human approval.
 */

import { createServerClient } from "@/lib/supabase";
import {
  placeOrder,
  getOrder,
  getPrice,
  BINANCE_CONFIG,
} from "@/lib/exchanges/binance-testnet";
import { logRiskEvent } from "./risk-manager";

// ============================================================================
// TYPES
// ============================================================================

export interface ExecutionResult {
  success: boolean;
  orderId?: number;
  executedPrice?: number;
  executedQuantity?: number;
  commission?: number;
  commissionAsset?: string;
  error?: string;
  details?: any;
}

export interface ProposalExecution {
  proposalId: string;
  type: "buy" | "sell";
  symbol: string;
  quantity: number;
  price?: number;
  orderType: "MARKET" | "LIMIT";
}

// ============================================================================
// MAIN EXECUTION FUNCTION
// ============================================================================

/**
 * Execute an approved trade proposal
 */
export async function executeTradeProposal(
  proposalId: string
): Promise<ExecutionResult> {
  const supabase = createServerClient();

  let proposal: any = null;

  try {
    // ========================================================================
    // FETCH AND VALIDATE PROPOSAL
    // ========================================================================

    const { data: proposalData, error: fetchError } = await supabase
      .from("trade_proposals")
      .select("*")
      .eq("id", proposalId)
      .single();

    proposal = proposalData;

    if (fetchError || !proposal) {
      return {
        success: false,
        error: "Proposal not found",
      };
    }

    // Validate status
    if (proposal.status !== "approved") {
      return {
        success: false,
        error: `Cannot execute proposal with status '${proposal.status}'. Only 'approved' proposals can be executed.`,
      };
    }

    // ========================================================================
    // SAFETY CHECK: Verify environment
    // ========================================================================

    if (BINANCE_CONFIG.ENV !== "spot_testnet") {
      await logRiskEvent(
        "execution_blocked",
        "critical",
        `Execution blocked: Invalid environment '${BINANCE_CONFIG.ENV}'`,
        { proposalId },
        undefined,
        proposalId
      );

      return {
        success: false,
        error: `SAFETY CHECK FAILED: BINANCE_ENV must be 'spot_testnet', got '${BINANCE_CONFIG.ENV}'`,
      };
    }

    // ========================================================================
    // PLACE ORDER ON BINANCE
    // ========================================================================

    let orderResult: any;

    try {
      const orderParams: any = {
        symbol: proposal.symbol,
        side: proposal.type.toUpperCase() as "BUY" | "SELL",
        type: proposal.order_type as "LIMIT" | "MARKET",
        quantity: Number(proposal.quantity),
      };

      if (proposal.order_type === "LIMIT") {
        orderParams.price = Number(proposal.price);
        orderParams.timeInForce = "GTC"; // Good Till Cancel
      }

      console.log("Placing order on Binance:", orderParams);

      orderResult = await placeOrder(orderParams);

      console.log("Order placed successfully:", orderResult);
    } catch (orderError) {
      // Order failed - update proposal and log
      const errorMessage =
        orderError instanceof Error ? orderError.message : String(orderError);

      const newRetryCount = (proposal.retry_count || 0) + 1;
      const isDeadLetter = newRetryCount >= 3;
      const newStatus = isDeadLetter ? "dead_letter" : "error";

      await supabase
        .from("trade_proposals")
        .update({
          status: newStatus,
          error_message: errorMessage,
          retry_count: newRetryCount,
          updated_at: new Date().toISOString(),
        })
        .eq("id", proposalId);

      await logRiskEvent(
        isDeadLetter ? "dead_letter" : "order_rejected",
        "critical",
        isDeadLetter
          ? `Dead letter after ${newRetryCount} failures: ${errorMessage}`
          : `Order rejected by exchange: ${errorMessage}`,
        {
          proposalId,
          symbol: proposal.symbol,
          retryCount: newRetryCount,
          orderParams: {
            symbol: proposal.symbol,
            side: proposal.type,
            type: proposal.order_type,
            quantity: proposal.quantity,
          },
        },
        undefined,
        proposalId
      );

      return {
        success: false,
        error: errorMessage,
        details: orderError,
      };
    }

    // ========================================================================
    // VERIFY ORDER EXECUTION
    // ========================================================================

    let executionDetails: any;

    try {
      // Get order details to confirm execution
      executionDetails = await getOrder(proposal.symbol, orderResult.orderId);
    } catch (error) {
      console.warn("Failed to fetch order details:", error);
      executionDetails = orderResult; // Fallback to order result
    }

    // Extract execution details (with NaN safety)
    const rawPrice =
      executionDetails.price && Number(executionDetails.price) > 0
        ? Number(executionDetails.price)
        : executionDetails.fills?.[0]?.price
          ? Number(executionDetails.fills[0].price)
          : proposal.price
            ? Number(proposal.price)
            : 0;
    const executedPrice = Number.isFinite(rawPrice) ? rawPrice : 0;

    const rawQuantity = Number(
      executionDetails.executedQty || proposal.quantity
    );
    const executedQuantity = Number.isFinite(rawQuantity) ? rawQuantity : 0;

    const commission = executionDetails.fills
      ? executionDetails.fills.reduce(
          (sum: number, fill: any) => sum + (Number(fill.commission) || 0),
          0
        )
      : 0;

    if (executedPrice <= 0 || executedQuantity <= 0) {
      console.error("Invalid execution values:", { executedPrice, executedQuantity });
      return {
        success: false,
        error: `Invalid execution data: price=${executedPrice}, quantity=${executedQuantity}`,
      };
    }

    const commissionAsset = executionDetails.fills?.[0]?.commissionAsset;

    // ========================================================================
    // UPDATE PROPOSAL STATUS
    // ========================================================================

    const { error: updateError } = await supabase
      .from("trade_proposals")
      .update({
        status: "executed",
        binance_order_id: orderResult.orderId,
        executed_price: executedPrice,
        executed_quantity: executedQuantity,
        commission,
        commission_asset: commissionAsset,
        executed_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq("id", proposalId);

    if (updateError) {
      console.error("Failed to update proposal after execution:", updateError);
    }

    // ========================================================================
    // CREATE OR UPDATE POSITION
    // ========================================================================

    if (proposal.type === "buy") {
      // Opening new position
      await createPosition({
        symbol: proposal.symbol,
        side: "long",
        entryPrice: executedPrice,
        entryQuantity: executedQuantity,
        entryOrderId: orderResult.orderId,
        entryProposalId: proposalId,
        strategyId: proposal.strategy_id,
        commission,
        commissionAsset,
      });
    } else {
      // Closing position (sell)
      await closePosition({
        symbol: proposal.symbol,
        exitPrice: executedPrice,
        exitQuantity: executedQuantity,
        exitOrderId: orderResult.orderId,
        exitProposalId: proposalId,
        commission,
        commissionAsset,
      });
    }

    // ========================================================================
    // LOG SUCCESS EVENT
    // ========================================================================

    await logRiskEvent(
      "order_executed",
      "info",
      `Order executed successfully: ${proposal.type.toUpperCase()} ${executedQuantity} ${proposal.symbol} @ ${executedPrice}`,
      {
        proposalId,
        orderId: orderResult.orderId,
        symbol: proposal.symbol,
        type: proposal.type,
        executedPrice,
        executedQuantity,
        commission,
      },
      undefined,
      proposalId
    );

    // ========================================================================
    // RETURN SUCCESS
    // ========================================================================

    return {
      success: true,
      orderId: orderResult.orderId,
      executedPrice,
      executedQuantity,
      commission,
      commissionAsset,
      details: executionDetails,
    };
  } catch (error) {
    console.error("Execution error:", error);

    const errorMessage =
      error instanceof Error ? error.message : String(error);

    const newRetryCount = proposal?.retry_count ? proposal.retry_count + 1 : 1;
    const isDeadLetter = newRetryCount >= 3;
    const newStatus = isDeadLetter ? "dead_letter" : "error";

    // Update proposal status
    await supabase
      .from("trade_proposals")
      .update({
        status: newStatus,
        error_message: errorMessage,
        retry_count: newRetryCount,
        updated_at: new Date().toISOString(),
      })
      .eq("id", proposalId);

    await logRiskEvent(
      isDeadLetter ? "dead_letter" : "execution_error",
      "critical",
      isDeadLetter
        ? `Dead letter after ${newRetryCount} failures: ${errorMessage}`
        : `Execution failed: ${errorMessage}`,
      { proposalId, error: errorMessage, retryCount: newRetryCount },
      undefined,
      proposalId
    );

    return {
      success: false,
      error: errorMessage,
    };
  }
}

// ============================================================================
// POSITION MANAGEMENT
// ============================================================================

async function createPosition(params: {
  symbol: string;
  side: "long" | "short";
  entryPrice: number;
  entryQuantity: number;
  entryOrderId: number;
  entryProposalId: string;
  strategyId?: string;
  commission: number;
  commissionAsset?: string;
}) {
  const supabase = createServerClient();

  // Get current price for unrealized P&L calculation
  let currentPrice = params.entryPrice;
  try {
    const priceData = await getPrice(params.symbol);
    currentPrice = parseFloat(priceData.price);
  } catch (error) {
    console.warn("Failed to fetch current price:", error);
  }

  const entryNotional = params.entryPrice * params.entryQuantity;

  // Calculate unrealized P&L
  const unrealizedPnL =
    (currentPrice - params.entryPrice) * params.entryQuantity -
    params.commission;
  const unrealizedPnLPercent = (unrealizedPnL / entryNotional) * 100;

  const { data: position, error } = await supabase
    .from("positions")
    .insert({
      symbol: params.symbol,
      side: params.side,
      entry_price: params.entryPrice,
      entry_quantity: params.entryQuantity,
      entry_notional: entryNotional,
      entry_order_id: params.entryOrderId,
      entry_proposal_id: params.entryProposalId,
      current_price: currentPrice,
      current_quantity: params.entryQuantity,
      unrealized_pnl: unrealizedPnL,
      unrealized_pnl_percent: unrealizedPnLPercent,
      total_commission: params.commission,
      commission_asset: params.commissionAsset,
      strategy_id: params.strategyId,
      status: "open",
    })
    .select()
    .single();

  if (error) {
    console.error("Failed to create position:", error);
    throw error;
  }

  console.log("Position created:", position);
  return position;
}

async function closePosition(params: {
  symbol: string;
  exitPrice: number;
  exitQuantity: number;
  exitOrderId: number;
  exitProposalId: string;
  commission: number;
  commissionAsset?: string;
}) {
  const supabase = createServerClient();

  // Find open position for this symbol
  const { data: position, error: fetchError } = await supabase
    .from("positions")
    .select("*")
    .eq("symbol", params.symbol)
    .eq("status", "open")
    .order("opened_at", { ascending: false })
    .limit(1)
    .single();

  if (fetchError || !position) {
    console.error("No open position found for", params.symbol);
    throw new Error(`No open position found for ${params.symbol}`);
  }

  const exitNotional = params.exitPrice * params.exitQuantity;

  // Calculate realized P&L
  const priceDiff = params.exitPrice - Number(position.entry_price);
  const totalCommission = Number(position.total_commission) + params.commission;
  const realizedPnL = priceDiff * params.exitQuantity - totalCommission;
  const realizedPnLPercent =
    (realizedPnL / Number(position.entry_notional)) * 100;

  // Determine new status
  const remainingQuantity =
    Number(position.current_quantity) - params.exitQuantity;
  const newStatus =
    remainingQuantity <= 0 ? "closed" : "partially_closed";

  const updateData: any = {
    exit_price: params.exitPrice,
    exit_quantity: params.exitQuantity,
    exit_notional: exitNotional,
    exit_order_id: params.exitOrderId,
    exit_proposal_id: params.exitProposalId,
    current_quantity: remainingQuantity,
    realized_pnl: realizedPnL,
    realized_pnl_percent: realizedPnLPercent,
    total_commission: totalCommission,
    status: newStatus,
    updated_at: new Date().toISOString(),
  };

  if (newStatus === "closed") {
    updateData.closed_at = new Date().toISOString();
  }

  const { data: updatedPosition, error: updateError } = await supabase
    .from("positions")
    .update(updateData)
    .eq("id", position.id)
    .select()
    .single();

  if (updateError) {
    console.error("Failed to update position:", updateError);
    throw updateError;
  }

  console.log("Position updated:", updatedPosition);

  // Log P&L event
  await logRiskEvent(
    newStatus === "closed" ? "position_closed" : "position_partial_close",
    realizedPnL >= 0 ? "info" : "warning",
    `Position ${newStatus}: ${realizedPnL >= 0 ? "profit" : "loss"} of $${Math.abs(realizedPnL).toFixed(2)} (${realizedPnLPercent.toFixed(2)}%)`,
    {
      positionId: position.id,
      symbol: params.symbol,
      entryPrice: position.entry_price,
      exitPrice: params.exitPrice,
      quantity: params.exitQuantity,
      realizedPnL,
      realizedPnLPercent,
    },
    position.id
  );

  return updatedPosition;
}

// ============================================================================
// BATCH EXECUTION
// ============================================================================

/**
 * Execute all approved proposals
 */
export async function executeApprovedProposals(): Promise<{
  executed: number;
  failed: number;
  results: ExecutionResult[];
}> {
  const supabase = createServerClient();

  // Get all approved proposals
  const { data: proposals, error } = await supabase
    .from("trade_proposals")
    .select("id")
    .eq("status", "approved")
    .order("created_at", { ascending: true }); // FIFO

  if (error || !proposals || proposals.length === 0) {
    return { executed: 0, failed: 0, results: [] };
  }

  console.log(`Executing ${proposals.length} approved proposals...`);

  const results: ExecutionResult[] = [];
  let executed = 0;
  let failed = 0;

  for (const proposal of proposals) {
    const result = await executeTradeProposal(proposal.id);
    results.push(result);

    if (result.success) {
      executed++;
    } else {
      failed++;
    }

    // Small delay between executions to avoid rate limiting
    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  console.log(
    `Execution complete: ${executed} succeeded, ${failed} failed`
  );

  return { executed, failed, results };
}
