/**
 * Risk Manager - Deterministic validation for trade proposals
 *
 * Validates all trades against predefined risk limits before execution.
 * This is a DETERMINISTIC system - no LLM, pure rule-based validation.
 */

import { createServerClient } from "@/lib/supabase";

// ============================================================================
// RISK LIMITS (Configurable via env or database)
// ============================================================================

export interface RiskLimits {
  // Position sizing
  maxPositionSize: number; // Max $500 per trade
  minPositionSize: number; // Min $10 per trade

  // Loss limits
  maxDailyLoss: number; // Max -$200/day
  maxDrawdown: number; // Max -$1000 from peak balance

  // Position limits
  maxOpenPositions: number; // Max 3 positions simultaneously
  maxPositionsPerSymbol: number; // Max 1 position per symbol

  // Account health
  minAccountBalance: number; // Min $1000 to open new positions
  maxAccountUtilization: number; // Max 80% of balance in positions

  // Auto-approval
  autoApprovalThreshold: number; // Auto-approve if notional < $100
}

export const DEFAULT_RISK_LIMITS: RiskLimits = {
  maxPositionSize: 500,
  minPositionSize: 10,
  maxDailyLoss: 200,
  maxDrawdown: 1000,
  maxOpenPositions: 3,
  maxPositionsPerSymbol: 1,
  minAccountBalance: 1000,
  maxAccountUtilization: 0.8,
  autoApprovalThreshold: 100,
};

// ============================================================================
// TYPES
// ============================================================================

export interface TradeProposal {
  id?: string;
  type: "buy" | "sell";
  symbol: string;
  quantity: number;
  price?: number; // NULL for market orders
  orderType: "MARKET" | "LIMIT";
  notional: number; // quantity * price
  strategyId?: string;
  reasoning?: string;
}

export interface ValidationResult {
  approved: boolean;
  autoApproved: boolean;
  riskScore: number; // 0-100 (higher = riskier)
  checks: RiskCheck[];
  rejectionReason?: string;
}

export interface RiskCheck {
  name: string;
  passed: boolean;
  value?: number;
  limit?: number;
  severity: "info" | "warning" | "critical";
  message: string;
}

export interface AccountState {
  totalBalance: number;
  availableBalance: number;
  lockedBalance: number;
  openPositions: number;
  dailyPnL: number;
  currentDrawdown: number;
  peakBalance: number;
}

export interface PositionState {
  symbol: string;
  side: "long" | "short";
  quantity: number;
  entryPrice: number;
  currentPrice: number;
  unrealizedPnL: number;
}

// ============================================================================
// MAIN VALIDATION FUNCTION
// ============================================================================

/**
 * Validate a trade proposal against all risk limits
 */
export async function validateTradeProposal(
  proposal: TradeProposal,
  limits: RiskLimits = DEFAULT_RISK_LIMITS
): Promise<ValidationResult> {
  const checks: RiskCheck[] = [];
  let riskScore = 0;

  try {
    // Get current account state
    const accountState = await getAccountState();
    const openPositions = await getOpenPositions();
    const dailyLoss = await getDailyLoss();

    // ========================================================================
    // CHECK 1: Position Size
    // ========================================================================
    const positionSizeCheck = validatePositionSize(proposal, limits);
    checks.push(positionSizeCheck);
    if (!positionSizeCheck.passed) {
      riskScore += 30;
    } else {
      riskScore += 5;
    }

    // ========================================================================
    // CHECK 2: Account Balance
    // ========================================================================
    const balanceCheck = validateAccountBalance(
      proposal,
      accountState,
      limits
    );
    checks.push(balanceCheck);
    if (!balanceCheck.passed) {
      riskScore += 30;
    } else {
      riskScore += 5;
    }

    // ========================================================================
    // CHECK 3: Daily Loss Limit
    // ========================================================================
    const dailyLossCheck = validateDailyLoss(dailyLoss, limits);
    checks.push(dailyLossCheck);
    if (!dailyLossCheck.passed) {
      riskScore += 25;
    } else if (Math.abs(dailyLoss) > limits.maxDailyLoss * 0.5) {
      riskScore += 15; // Warning if > 50% of daily limit used
    } else {
      riskScore += 5;
    }

    // ========================================================================
    // CHECK 4: Drawdown Limit
    // ========================================================================
    const drawdownCheck = validateDrawdown(accountState, limits);
    checks.push(drawdownCheck);
    if (!drawdownCheck.passed) {
      riskScore += 25;
    } else if (accountState.currentDrawdown > limits.maxDrawdown * 0.5) {
      riskScore += 15; // Warning if > 50% of drawdown limit
    } else {
      riskScore += 5;
    }

    // ========================================================================
    // CHECK 5: Max Open Positions
    // ========================================================================
    const maxPositionsCheck = validateMaxPositions(
      proposal,
      openPositions,
      limits
    );
    checks.push(maxPositionsCheck);
    if (!maxPositionsCheck.passed) {
      riskScore += 20;
    } else {
      riskScore += 5;
    }

    // ========================================================================
    // CHECK 6: Symbol Concentration
    // ========================================================================
    const concentrationCheck = validateSymbolConcentration(
      proposal,
      openPositions,
      limits
    );
    checks.push(concentrationCheck);
    if (!concentrationCheck.passed) {
      riskScore += 15;
    } else {
      riskScore += 5;
    }

    // ========================================================================
    // CHECK 7: Account Utilization
    // ========================================================================
    const utilizationCheck = validateAccountUtilization(
      proposal,
      accountState,
      openPositions,
      limits
    );
    checks.push(utilizationCheck);
    if (!utilizationCheck.passed) {
      riskScore += 15;
    } else {
      riskScore += 5;
    }

    // ========================================================================
    // DETERMINE APPROVAL
    // ========================================================================

    const allChecksPassed = checks.every((check) => check.passed);
    const criticalFailures = checks.filter(
      (check) => !check.passed && check.severity === "critical"
    );

    if (!allChecksPassed) {
      return {
        approved: false,
        autoApproved: false,
        riskScore: Math.min(riskScore, 100),
        checks,
        rejectionReason:
          criticalFailures[0]?.message ||
          "Trade rejected due to risk limit violations",
      };
    }

    // Auto-approve if notional < threshold
    const autoApproved = proposal.notional < limits.autoApprovalThreshold;

    return {
      approved: true,
      autoApproved,
      riskScore: Math.min(riskScore, 100),
      checks,
    };
  } catch (error) {
    console.error("Error validating trade proposal:", error);

    // On error, reject with critical check
    checks.push({
      name: "System Health",
      passed: false,
      severity: "critical",
      message:
        error instanceof Error
          ? `Validation error: ${error.message}`
          : "Unknown validation error",
    });

    return {
      approved: false,
      autoApproved: false,
      riskScore: 100,
      checks,
      rejectionReason: "System error during validation",
    };
  }
}

// ============================================================================
// INDIVIDUAL CHECK FUNCTIONS
// ============================================================================

function validatePositionSize(
  proposal: TradeProposal,
  limits: RiskLimits
): RiskCheck {
  const { notional } = proposal;

  if (notional < limits.minPositionSize) {
    return {
      name: "Position Size (Min)",
      passed: false,
      value: notional,
      limit: limits.minPositionSize,
      severity: "critical",
      message: `Position size $${notional.toFixed(2)} is below minimum $${limits.minPositionSize}`,
    };
  }

  if (notional > limits.maxPositionSize) {
    return {
      name: "Position Size (Max)",
      passed: false,
      value: notional,
      limit: limits.maxPositionSize,
      severity: "critical",
      message: `Position size $${notional.toFixed(2)} exceeds maximum $${limits.maxPositionSize}`,
    };
  }

  return {
    name: "Position Size",
    passed: true,
    value: notional,
    limit: limits.maxPositionSize,
    severity: "info",
    message: `Position size $${notional.toFixed(2)} is within limits`,
  };
}

function validateAccountBalance(
  proposal: TradeProposal,
  accountState: AccountState,
  limits: RiskLimits
): RiskCheck {
  const { totalBalance, availableBalance } = accountState;
  const { notional } = proposal;

  // Check if account has minimum balance
  if (totalBalance < limits.minAccountBalance) {
    return {
      name: "Account Balance",
      passed: false,
      value: totalBalance,
      limit: limits.minAccountBalance,
      severity: "critical",
      message: `Account balance $${totalBalance.toFixed(2)} is below minimum $${limits.minAccountBalance}`,
    };
  }

  // Check if sufficient available balance for this trade
  if (availableBalance < notional) {
    return {
      name: "Available Balance",
      passed: false,
      value: availableBalance,
      limit: notional,
      severity: "critical",
      message: `Insufficient balance: need $${notional.toFixed(2)}, have $${availableBalance.toFixed(2)}`,
    };
  }

  return {
    name: "Account Balance",
    passed: true,
    value: availableBalance,
    severity: "info",
    message: `Sufficient balance available: $${availableBalance.toFixed(2)}`,
  };
}

function validateDailyLoss(dailyLoss: number, limits: RiskLimits): RiskCheck {
  const absLoss = Math.abs(dailyLoss);

  if (absLoss >= limits.maxDailyLoss) {
    return {
      name: "Daily Loss Limit",
      passed: false,
      value: absLoss,
      limit: limits.maxDailyLoss,
      severity: "critical",
      message: `Daily loss $${absLoss.toFixed(2)} has reached limit of $${limits.maxDailyLoss}`,
    };
  }

  // Warning if > 75% of limit
  if (absLoss > limits.maxDailyLoss * 0.75) {
    return {
      name: "Daily Loss Limit",
      passed: true,
      value: absLoss,
      limit: limits.maxDailyLoss,
      severity: "warning",
      message: `Daily loss $${absLoss.toFixed(2)} approaching limit ($${limits.maxDailyLoss})`,
    };
  }

  return {
    name: "Daily Loss Limit",
    passed: true,
    value: absLoss,
    limit: limits.maxDailyLoss,
    severity: "info",
    message: `Daily P&L: $${dailyLoss.toFixed(2)}`,
  };
}

function validateDrawdown(
  accountState: AccountState,
  limits: RiskLimits
): RiskCheck {
  const { currentDrawdown, totalBalance, peakBalance } = accountState;
  const drawdownPercent =
    peakBalance > 0 ? (currentDrawdown / peakBalance) * 100 : 0;

  if (currentDrawdown >= limits.maxDrawdown) {
    return {
      name: "Drawdown Limit",
      passed: false,
      value: currentDrawdown,
      limit: limits.maxDrawdown,
      severity: "critical",
      message: `Drawdown $${currentDrawdown.toFixed(2)} (${drawdownPercent.toFixed(1)}%) has reached limit of $${limits.maxDrawdown}`,
    };
  }

  // Warning if > 75% of limit
  if (currentDrawdown > limits.maxDrawdown * 0.75) {
    return {
      name: "Drawdown Limit",
      passed: true,
      value: currentDrawdown,
      limit: limits.maxDrawdown,
      severity: "warning",
      message: `Drawdown $${currentDrawdown.toFixed(2)} (${drawdownPercent.toFixed(1)}%) approaching limit`,
    };
  }

  return {
    name: "Drawdown Limit",
    passed: true,
    value: currentDrawdown,
    limit: limits.maxDrawdown,
    severity: "info",
    message: `Current drawdown: $${currentDrawdown.toFixed(2)} (${drawdownPercent.toFixed(1)}%)`,
  };
}

function validateMaxPositions(
  proposal: TradeProposal,
  openPositions: PositionState[],
  limits: RiskLimits
): RiskCheck {
  const currentOpenPositions = openPositions.length;

  // Only check for new positions (buy), not closes (sell)
  if (proposal.type === "sell") {
    return {
      name: "Max Open Positions",
      passed: true,
      value: currentOpenPositions,
      limit: limits.maxOpenPositions,
      severity: "info",
      message: "Closing position (does not count against limit)",
    };
  }

  if (currentOpenPositions >= limits.maxOpenPositions) {
    return {
      name: "Max Open Positions",
      passed: false,
      value: currentOpenPositions,
      limit: limits.maxOpenPositions,
      severity: "critical",
      message: `Already at maximum of ${limits.maxOpenPositions} open positions`,
    };
  }

  return {
    name: "Max Open Positions",
    passed: true,
    value: currentOpenPositions,
    limit: limits.maxOpenPositions,
    severity: "info",
    message: `${currentOpenPositions} of ${limits.maxOpenPositions} positions open`,
  };
}

function validateSymbolConcentration(
  proposal: TradeProposal,
  openPositions: PositionState[],
  limits: RiskLimits
): RiskCheck {
  // Only check for new positions (buy)
  if (proposal.type === "sell") {
    return {
      name: "Symbol Concentration",
      passed: true,
      severity: "info",
      message: "Closing position (does not count against limit)",
    };
  }

  const positionsInSymbol = openPositions.filter(
    (pos) => pos.symbol === proposal.symbol
  ).length;

  if (positionsInSymbol >= limits.maxPositionsPerSymbol) {
    return {
      name: "Symbol Concentration",
      passed: false,
      value: positionsInSymbol,
      limit: limits.maxPositionsPerSymbol,
      severity: "critical",
      message: `Already have ${positionsInSymbol} position(s) in ${proposal.symbol}`,
    };
  }

  return {
    name: "Symbol Concentration",
    passed: true,
    value: positionsInSymbol,
    limit: limits.maxPositionsPerSymbol,
    severity: "info",
    message: `${positionsInSymbol} of ${limits.maxPositionsPerSymbol} positions in ${proposal.symbol}`,
  };
}

function validateAccountUtilization(
  proposal: TradeProposal,
  accountState: AccountState,
  openPositions: PositionState[],
  limits: RiskLimits
): RiskCheck {
  const { totalBalance } = accountState;

  // Calculate total notional in open positions
  const totalInPositions = openPositions.reduce(
    (sum, pos) => sum + pos.quantity * pos.entryPrice,
    0
  );

  // Add proposed trade
  const newTotal = totalInPositions + proposal.notional;
  const utilizationPercent = (newTotal / totalBalance) * 100;
  const maxUtilizationPercent = limits.maxAccountUtilization * 100;

  if (utilizationPercent > maxUtilizationPercent) {
    return {
      name: "Account Utilization",
      passed: false,
      value: utilizationPercent,
      limit: maxUtilizationPercent,
      severity: "critical",
      message: `Account utilization ${utilizationPercent.toFixed(1)}% exceeds maximum ${maxUtilizationPercent}%`,
    };
  }

  // Warning if > 70%
  if (utilizationPercent > 70) {
    return {
      name: "Account Utilization",
      passed: true,
      value: utilizationPercent,
      limit: maxUtilizationPercent,
      severity: "warning",
      message: `High account utilization: ${utilizationPercent.toFixed(1)}%`,
    };
  }

  return {
    name: "Account Utilization",
    passed: true,
    value: utilizationPercent,
    limit: maxUtilizationPercent,
    severity: "info",
    message: `Account utilization: ${utilizationPercent.toFixed(1)}%`,
  };
}

// ============================================================================
// DATA FETCHING HELPERS
// ============================================================================

async function getAccountState(): Promise<AccountState> {
  const supabase = createServerClient();

  // Get latest snapshot
  const { data: snapshot } = await supabase
    .from("account_snapshots")
    .select("*")
    .order("snapshot_date", { ascending: false })
    .limit(1)
    .single();

  if (snapshot) {
    return {
      totalBalance: Number(snapshot.total_balance),
      availableBalance: Number(snapshot.available_balance),
      lockedBalance: Number(snapshot.locked_balance),
      openPositions: snapshot.open_positions,
      dailyPnL: Number(snapshot.daily_pnl) || 0,
      currentDrawdown: Number(snapshot.current_drawdown) || 0,
      peakBalance: Number(snapshot.peak_balance),
    };
  }

  // If no snapshot, fetch from Binance
  const { getBalance } = await import("@/lib/exchanges/binance-testnet");

  const usdtBalance = await getBalance("USDT");
  const totalBalance =
    Number(usdtBalance.free) + Number(usdtBalance.locked);

  return {
    totalBalance,
    availableBalance: Number(usdtBalance.free),
    lockedBalance: Number(usdtBalance.locked),
    openPositions: 0,
    dailyPnL: 0,
    currentDrawdown: 0,
    peakBalance: totalBalance,
  };
}

async function getOpenPositions(): Promise<PositionState[]> {
  const supabase = createServerClient();

  const { data: positions } = await supabase
    .from("positions")
    .select("*")
    .eq("status", "open");

  if (!positions) return [];

  return positions.map((pos) => ({
    symbol: pos.symbol,
    side: pos.side,
    quantity: Number(pos.current_quantity),
    entryPrice: Number(pos.entry_price),
    currentPrice: Number(pos.current_price) || Number(pos.entry_price),
    unrealizedPnL: Number(pos.unrealized_pnl) || 0,
  }));
}

async function getDailyLoss(): Promise<number> {
  const supabase = createServerClient();

  // Get today's snapshot
  const today = new Date().toISOString().split("T")[0];

  const { data: snapshot } = await supabase
    .from("account_snapshots")
    .select("daily_pnl")
    .eq("snapshot_date", today)
    .single();

  if (snapshot) {
    return Number(snapshot.daily_pnl) || 0;
  }

  // If no snapshot today, calculate from positions closed today
  const { data: closedToday } = await supabase
    .from("positions")
    .select("realized_pnl")
    .eq("status", "closed")
    .gte("closed_at", new Date().toISOString().split("T")[0]);

  if (!closedToday || closedToday.length === 0) return 0;

  return closedToday.reduce((sum, pos) => sum + Number(pos.realized_pnl), 0);
}

// ============================================================================
// RISK EVENT LOGGING
// ============================================================================

export async function logRiskEvent(
  eventType: string,
  severity: "info" | "warning" | "critical",
  message: string,
  details?: any,
  positionId?: string,
  proposalId?: string
) {
  const supabase = createServerClient();

  await supabase.from("risk_events").insert({
    event_type: eventType,
    severity,
    message,
    details,
    position_id: positionId,
    proposal_id: proposalId,
  });
}
