-- Trading System Tables Migration
-- Created: 2026-02-16
-- Purpose: Add tables for trade execution, positions, and risk management

-- ============================================================================
-- TRADE PROPOSALS (HITL - Human in the Loop)
-- ============================================================================
CREATE TABLE IF NOT EXISTS trade_proposals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Strategy reference
  strategy_id UUID REFERENCES strategies_found(id) ON DELETE SET NULL,

  -- Trade details
  type TEXT NOT NULL CHECK (type IN ('buy', 'sell')),
  symbol TEXT NOT NULL, -- 'BTCUSDT', 'ETHUSDT', etc.
  quantity DECIMAL(20, 8) NOT NULL CHECK (quantity > 0),
  price DECIMAL(20, 8), -- NULL for market orders
  order_type TEXT NOT NULL DEFAULT 'MARKET' CHECK (order_type IN ('MARKET', 'LIMIT')),
  time_in_force TEXT CHECK (time_in_force IN ('GTC', 'IOC', 'FOK')), -- Only for LIMIT orders

  -- Calculated values
  notional DECIMAL(20, 8) NOT NULL, -- quantity * price (estimated for market orders)

  -- Status workflow: draft -> validated -> approved/rejected -> executed
  status TEXT NOT NULL DEFAULT 'draft' CHECK (
    status IN ('draft', 'validated', 'approved', 'rejected', 'executed', 'error')
  ),

  -- Risk assessment
  risk_score DECIMAL(5, 2) CHECK (risk_score >= 0 AND risk_score <= 100),
  risk_checks JSONB, -- Detailed risk validation results

  -- Auto-approval logic
  auto_approved BOOLEAN DEFAULT false,
  approval_threshold DECIMAL(20, 8) DEFAULT 100.00, -- Auto-approve if notional < $100

  -- LLM reasoning
  reasoning TEXT, -- Why this trade was proposed
  market_conditions JSONB, -- Snapshot of market data at proposal time

  -- Execution details
  binance_order_id BIGINT, -- Binance order ID after execution
  executed_price DECIMAL(20, 8), -- Actual execution price
  executed_quantity DECIMAL(20, 8), -- Actual quantity filled
  commission DECIMAL(20, 8), -- Trading fee
  commission_asset TEXT, -- Asset used for fee (usually USDT or BNB)

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  validated_at TIMESTAMPTZ,
  approved_at TIMESTAMPTZ,
  rejected_at TIMESTAMPTZ,
  executed_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- Error handling
  error_message TEXT,
  retry_count INTEGER DEFAULT 0
);

-- Indexes for trade_proposals
CREATE INDEX idx_trade_proposals_status ON trade_proposals(status);
CREATE INDEX idx_trade_proposals_symbol ON trade_proposals(symbol);
CREATE INDEX idx_trade_proposals_created_at ON trade_proposals(created_at DESC);
CREATE INDEX idx_trade_proposals_strategy_id ON trade_proposals(strategy_id);

-- ============================================================================
-- POSITIONS (Open & Closed)
-- ============================================================================
CREATE TABLE IF NOT EXISTS positions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Position details
  symbol TEXT NOT NULL, -- 'BTCUSDT', 'ETHUSDT', etc.
  side TEXT NOT NULL CHECK (side IN ('long', 'short')),

  -- Entry details
  entry_price DECIMAL(20, 8) NOT NULL CHECK (entry_price > 0),
  entry_quantity DECIMAL(20, 8) NOT NULL CHECK (entry_quantity > 0),
  entry_notional DECIMAL(20, 8) NOT NULL, -- entry_price * entry_quantity
  entry_order_id BIGINT, -- Binance order ID

  -- Current state (for open positions)
  current_price DECIMAL(20, 8),
  current_quantity DECIMAL(20, 8) NOT NULL, -- Can be partially closed

  -- Exit details (for closed positions)
  exit_price DECIMAL(20, 8),
  exit_quantity DECIMAL(20, 8),
  exit_notional DECIMAL(20, 8),
  exit_order_id BIGINT,

  -- P&L calculation
  realized_pnl DECIMAL(20, 8), -- Profit/loss in USDT
  realized_pnl_percent DECIMAL(10, 4), -- Percentage return
  unrealized_pnl DECIMAL(20, 8), -- For open positions
  unrealized_pnl_percent DECIMAL(10, 4),

  -- Commission tracking
  total_commission DECIMAL(20, 8) DEFAULT 0,
  commission_asset TEXT,

  -- Status
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'partially_closed')),

  -- Stop loss & take profit (if set)
  stop_loss_price DECIMAL(20, 8),
  take_profit_price DECIMAL(20, 8),
  stop_loss_order_id BIGINT,
  take_profit_order_id BIGINT,

  -- Strategy reference
  strategy_id UUID REFERENCES strategies_found(id) ON DELETE SET NULL,
  entry_proposal_id UUID REFERENCES trade_proposals(id) ON DELETE SET NULL,
  exit_proposal_id UUID REFERENCES trade_proposals(id) ON DELETE SET NULL,

  -- Timestamps
  opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  closed_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for positions
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_opened_at ON positions(opened_at DESC);
CREATE INDEX idx_positions_strategy_id ON positions(strategy_id);

-- ============================================================================
-- RISK EVENTS (Alerts & Violations)
-- ============================================================================
CREATE TABLE IF NOT EXISTS risk_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Event classification
  event_type TEXT NOT NULL CHECK (
    event_type IN (
      'limit_hit',           -- Risk limit reached
      'drawdown_alert',      -- Drawdown threshold breached
      'daily_loss_limit',    -- Daily loss limit hit
      'position_size_limit', -- Position too large
      'margin_call',         -- Insufficient balance
      'max_positions',       -- Too many open positions
      'price_spike',         -- Unusual price movement
      'connection_loss',     -- Exchange connection issues
      'order_rejected'       -- Order rejected by exchange
    )
  ),

  -- Severity
  severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),

  -- Details
  message TEXT NOT NULL,
  details JSONB, -- Structured data about the event

  -- References
  position_id UUID REFERENCES positions(id) ON DELETE SET NULL,
  proposal_id UUID REFERENCES trade_proposals(id) ON DELETE SET NULL,

  -- Resolution
  resolved BOOLEAN DEFAULT false,
  resolved_at TIMESTAMPTZ,
  resolved_by TEXT, -- 'auto' or user identifier
  resolution_notes TEXT,

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for risk_events
CREATE INDEX idx_risk_events_severity ON risk_events(severity);
CREATE INDEX idx_risk_events_resolved ON risk_events(resolved);
CREATE INDEX idx_risk_events_created_at ON risk_events(created_at DESC);
CREATE INDEX idx_risk_events_event_type ON risk_events(event_type);

-- ============================================================================
-- ACCOUNT SNAPSHOTS (Daily balance tracking)
-- ============================================================================
CREATE TABLE IF NOT EXISTS account_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Balance details
  total_balance DECIMAL(20, 8) NOT NULL, -- Total account value in USDT
  available_balance DECIMAL(20, 8) NOT NULL, -- Free balance
  locked_balance DECIMAL(20, 8) NOT NULL, -- In orders

  -- Asset breakdown
  balances JSONB NOT NULL, -- { "USDT": { "free": "1000", "locked": "0" }, ... }

  -- Performance metrics
  daily_pnl DECIMAL(20, 8),
  daily_pnl_percent DECIMAL(10, 4),
  total_pnl DECIMAL(20, 8), -- All-time P&L
  total_pnl_percent DECIMAL(10, 4),

  -- High watermark (for drawdown calculation)
  peak_balance DECIMAL(20, 8),
  current_drawdown DECIMAL(20, 8),
  current_drawdown_percent DECIMAL(10, 4),
  max_drawdown DECIMAL(20, 8),
  max_drawdown_percent DECIMAL(10, 4),

  -- Position counts
  open_positions INTEGER DEFAULT 0,
  total_trades INTEGER DEFAULT 0,
  winning_trades INTEGER DEFAULT 0,
  losing_trades INTEGER DEFAULT 0,

  -- Win rate
  win_rate DECIMAL(5, 2), -- Percentage

  -- Timestamps
  snapshot_date DATE NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for account_snapshots
CREATE INDEX idx_account_snapshots_date ON account_snapshots(snapshot_date DESC);

-- ============================================================================
-- MARKET DATA CACHE (WebSocket data storage)
-- ============================================================================
CREATE TABLE IF NOT EXISTS market_data (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Symbol
  symbol TEXT NOT NULL,

  -- Price data
  price DECIMAL(20, 8) NOT NULL,
  bid_price DECIMAL(20, 8),
  ask_price DECIMAL(20, 8),

  -- 24h statistics
  high_24h DECIMAL(20, 8),
  low_24h DECIMAL(20, 8),
  volume_24h DECIMAL(20, 8),
  price_change_24h DECIMAL(20, 8),
  price_change_percent_24h DECIMAL(10, 4),

  -- Order book depth (top 5 levels)
  bids JSONB, -- [["price", "quantity"], ...]
  asks JSONB,

  -- Timestamp
  exchange_timestamp TIMESTAMPTZ,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for market_data
CREATE INDEX idx_market_data_symbol ON market_data(symbol);
CREATE INDEX idx_market_data_received_at ON market_data(received_at DESC);

-- Keep only last 24 hours of market data (optional cleanup)
-- Can be run periodically via cron
-- DELETE FROM market_data WHERE received_at < NOW() - INTERVAL '24 hours';

-- ============================================================================
-- TRIGGERS for updated_at timestamps
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to trade_proposals
CREATE TRIGGER update_trade_proposals_updated_at
  BEFORE UPDATE ON trade_proposals
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to positions
CREATE TRIGGER update_positions_updated_at
  BEFORE UPDATE ON positions
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE trade_proposals IS 'Trade proposals requiring human approval (HITL)';
COMMENT ON TABLE positions IS 'Open and closed trading positions';
COMMENT ON TABLE risk_events IS 'Risk management alerts and violations';
COMMENT ON TABLE account_snapshots IS 'Daily account balance and performance snapshots';
COMMENT ON TABLE market_data IS 'Real-time market data cache from WebSocket';

COMMENT ON COLUMN trade_proposals.notional IS 'Total value of trade in USDT (quantity * price)';
COMMENT ON COLUMN trade_proposals.auto_approved IS 'True if trade was auto-approved due to low notional value';
COMMENT ON COLUMN positions.realized_pnl IS 'Actual profit/loss after closing position';
COMMENT ON COLUMN positions.unrealized_pnl IS 'Current profit/loss for open positions';
COMMENT ON COLUMN account_snapshots.peak_balance IS 'All-time high balance (for drawdown calculation)';
