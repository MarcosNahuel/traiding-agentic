/**
 * TypeScript types for API responses
 * Use these types in your frontend components
 */

// ============================================================================
// TRADING TYPES
// ============================================================================

export interface TradeProposal {
  id: string;
  strategy_id: string | null;
  type: "buy" | "sell";
  symbol: string;
  quantity: number;
  price: number | null;
  order_type: "MARKET" | "LIMIT";
  time_in_force: "GTC" | "IOC" | "FOK" | null;
  notional: number;
  status: "draft" | "validated" | "approved" | "rejected" | "executed" | "error";
  risk_score: number | null;
  risk_checks: RiskCheck[] | null;
  auto_approved: boolean;
  approval_threshold: number;
  reasoning: string | null;
  market_conditions: any;
  binance_order_id: number | null;
  executed_price: number | null;
  executed_quantity: number | null;
  commission: number | null;
  commission_asset: string | null;
  created_at: string;
  validated_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  executed_at: string | null;
  updated_at: string;
  error_message: string | null;
  retry_count: number;
}

export interface RiskCheck {
  name: string;
  passed: boolean;
  value?: number;
  limit?: number;
  severity: "info" | "warning" | "critical";
  message: string;
}

export interface Position {
  id: string;
  symbol: string;
  side: "long" | "short";
  entry_price: number;
  entry_quantity: number;
  entry_notional: number;
  entry_order_id: number | null;
  current_price: number | null;
  current_quantity: number;
  exit_price: number | null;
  exit_quantity: number | null;
  exit_notional: number | null;
  exit_order_id: number | null;
  realized_pnl: number | null;
  realized_pnl_percent: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_percent: number | null;
  total_commission: number;
  commission_asset: string | null;
  status: "open" | "closed" | "partially_closed";
  stop_loss_price: number | null;
  take_profit_price: number | null;
  stop_loss_order_id: number | null;
  take_profit_order_id: number | null;
  strategy_id: string | null;
  entry_proposal_id: string | null;
  exit_proposal_id: string | null;
  opened_at: string;
  closed_at: string | null;
  updated_at: string;
}

export interface RiskEvent {
  id: string;
  event_type: string;
  severity: "info" | "warning" | "critical";
  message: string;
  details: any;
  position_id: string | null;
  proposal_id: string | null;
  resolved: boolean;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution_notes: string | null;
  created_at: string;
}

export interface AccountSnapshot {
  id: string;
  total_balance: number;
  available_balance: number;
  locked_balance: number;
  balances: Record<string, { free: number; locked: number }>;
  daily_pnl: number | null;
  daily_pnl_percent: number | null;
  total_pnl: number | null;
  total_pnl_percent: number | null;
  peak_balance: number | null;
  current_drawdown: number | null;
  current_drawdown_percent: number | null;
  max_drawdown: number | null;
  max_drawdown_percent: number | null;
  open_positions: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number | null;
  snapshot_date: string;
  created_at: string;
}

// ============================================================================
// API RESPONSE TYPES
// ============================================================================

export interface TradeProposalsResponse {
  proposals: TradeProposal[];
  total: number;
  limit: number;
  offset: number;
  stats?: {
    pending: number;
    approved: number;
    rejected: number;
    executed: number;
  };
}

export interface PortfolioResponse {
  timestamp: string;
  balance: {
    total: number;
    available: number;
    locked: number;
    inPositions: number;
  };
  assets: {
    [key: string]: {
      free: number;
      locked: number;
      total: number;
    };
  };
  positions: {
    open: Position[];
    openCount: number;
    totalValue: number;
    totalUnrealizedPnL: number;
  };
  pnl: {
    daily: {
      realized: number;
      unrealized: number;
      total: number;
    };
    allTime: {
      realized: number;
      unrealized: number;
      total: number;
    };
  };
  performance: {
    totalTrades: number;
    winningTrades: number;
    losingTrades: number;
    winRate: string;
    avgWin: string;
    avgLoss: string;
  };
  risk: {
    currentDrawdown: number;
    currentDrawdownPercent: string;
    maxDrawdown: number;
    maxDrawdownPercent: string;
    peakBalance: number;
    unresolvedRiskEvents: number;
  };
  recentActivity: {
    closedToday: number;
    riskEvents: RiskEvent[];
  };
}

export interface PositionsHistoryResponse {
  positions: Position[];
  total: number;
  limit: number;
  offset: number;
  summary: {
    totalPnL: string;
    avgPnL: string;
    winningTrades: number;
    losingTrades: number;
    winRate: string;
    bestTrade: {
      symbol: string;
      pnl: string;
      pnlPercent: string;
      date: string;
    } | null;
    worstTrade: {
      symbol: string;
      pnl: string;
      pnlPercent: string;
      date: string;
    } | null;
  };
}

export interface RiskEventsResponse {
  events: RiskEvent[];
  total: number;
  limit: number;
  offset: number;
  summary: {
    total: number;
    critical: number;
    warning: number;
    info: number;
    unresolved: number;
  };
}

// ============================================================================
// RESEARCH TYPES
// ============================================================================

export interface Source {
  id: string;
  url: string;
  title: string | null;
  source_type: "paper" | "article" | "repo" | "book" | "video";
  status: string;
  quality_score: number | null;
  relevance_score: number | null;
  credibility_score: number | null;
  applicability_score: number | null;
  overall_score: number | null;
  raw_content: string | null;
  content_length: number | null;
  created_at: string;
  updated_at: string;
  fetched_at: string | null;
  error_message: string | null;
}

export interface Strategy {
  id: string;
  name: string;
  description: string;
  strategy_type: string;
  market: string;
  timeframe: string | null;
  confidence: number;
  evidence_strength: string;
  indicators: string[] | null;
  entry_rules: string[] | null;
  exit_rules: string[] | null;
  risk_management: string[] | null;
  limitations: string[] | null;
  parameters: any;
  source_id: string;
  validation_status: string;
  created_at: string;
}

export interface Guide {
  id: string;
  version: number;
  based_on_sources: number;
  based_on_strategies: number;
  confidence_score: number | null;
  executive_summary: string | null;
  full_guide_markdown: string;
  created_at: string;
}

// ============================================================================
// REQUEST TYPES
// ============================================================================

export interface CreateProposalRequest {
  type: "buy" | "sell";
  symbol: string;
  quantity: number;
  price?: number;
  orderType: "MARKET" | "LIMIT";
  strategyId?: string;
  reasoning?: string;
}

export interface ApproveProposalRequest {
  action: "approve" | "reject";
  notes?: string;
}

export interface ExecuteTradeRequest {
  proposalId?: string;
  executeAll?: boolean;
}

export interface AddSourceRequest {
  url: string;
  sourceType: "paper" | "article" | "repo" | "book" | "video";
}
