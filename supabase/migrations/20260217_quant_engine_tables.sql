-- Quant Engine Tables Migration
-- Created: 2026-02-17
-- Purpose: Add tables for quantitative analysis engine (indicators, entropy, regime, S/R, backtesting)

-- ============================================================================
-- KLINES OHLCV (Candlestick data from Binance)
-- ============================================================================
CREATE TABLE IF NOT EXISTS klines_ohlcv (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol TEXT NOT NULL,
  interval TEXT NOT NULL CHECK (interval IN ('1m', '5m', '15m', '1h', '4h', '1d')),
  open_time TIMESTAMPTZ NOT NULL,
  close_time TIMESTAMPTZ NOT NULL,
  open DECIMAL(20, 8) NOT NULL,
  high DECIMAL(20, 8) NOT NULL,
  low DECIMAL(20, 8) NOT NULL,
  close DECIMAL(20, 8) NOT NULL,
  volume DECIMAL(30, 8) NOT NULL,
  quote_volume DECIMAL(30, 8),
  trades_count INTEGER,
  taker_buy_base_volume DECIMAL(30, 8),
  taker_buy_quote_volume DECIMAL(30, 8),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT klines_ohlcv_unique UNIQUE (symbol, interval, open_time)
);

CREATE INDEX idx_klines_symbol_interval ON klines_ohlcv(symbol, interval);
CREATE INDEX idx_klines_open_time ON klines_ohlcv(open_time DESC);
CREATE INDEX idx_klines_symbol_interval_time ON klines_ohlcv(symbol, interval, open_time DESC);

-- ============================================================================
-- TECHNICAL INDICATORS (Calculated per candle)
-- ============================================================================
CREATE TABLE IF NOT EXISTS technical_indicators (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol TEXT NOT NULL,
  interval TEXT NOT NULL,
  candle_time TIMESTAMPTZ NOT NULL,

  -- Trend
  sma_20 DECIMAL(20, 8),
  sma_50 DECIMAL(20, 8),
  sma_200 DECIMAL(20, 8),
  ema_12 DECIMAL(20, 8),
  ema_26 DECIMAL(20, 8),
  ema_50 DECIMAL(20, 8),

  -- Momentum
  rsi_14 DECIMAL(10, 4),
  macd_line DECIMAL(20, 8),
  macd_signal DECIMAL(20, 8),
  macd_histogram DECIMAL(20, 8),
  stoch_k DECIMAL(10, 4),
  stoch_d DECIMAL(10, 4),
  adx_14 DECIMAL(10, 4),

  -- Volatility
  bb_upper DECIMAL(20, 8),
  bb_middle DECIMAL(20, 8),
  bb_lower DECIMAL(20, 8),
  bb_bandwidth DECIMAL(10, 6),
  atr_14 DECIMAL(20, 8),

  -- Volume
  obv DECIMAL(30, 8),
  vwap DECIMAL(20, 8),

  -- Meta
  calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT technical_indicators_unique UNIQUE (symbol, interval, candle_time)
);

CREATE INDEX idx_tech_ind_symbol_interval ON technical_indicators(symbol, interval);
CREATE INDEX idx_tech_ind_candle_time ON technical_indicators(candle_time DESC);

-- ============================================================================
-- MARKET REGIMES (Classification per symbol)
-- ============================================================================
CREATE TABLE IF NOT EXISTS market_regimes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol TEXT NOT NULL,
  interval TEXT NOT NULL,
  regime TEXT NOT NULL CHECK (regime IN ('trending_up', 'trending_down', 'ranging', 'volatile', 'low_liquidity')),
  confidence DECIMAL(5, 2) CHECK (confidence >= 0 AND confidence <= 100),

  -- Features used for classification
  adx_value DECIMAL(10, 4),
  bb_bandwidth DECIMAL(10, 6),
  atr_close_ratio DECIMAL(10, 6),
  hurst_exponent DECIMAL(10, 6),

  -- Meta
  detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT market_regimes_unique UNIQUE (symbol, interval)
);

CREATE INDEX idx_market_regimes_symbol ON market_regimes(symbol);

-- ============================================================================
-- SUPPORT/RESISTANCE LEVELS (K-Means clusters)
-- ============================================================================
CREATE TABLE IF NOT EXISTS support_resistance_levels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol TEXT NOT NULL,
  interval TEXT NOT NULL,
  level_type TEXT NOT NULL CHECK (level_type IN ('support', 'resistance')),
  price_level DECIMAL(20, 8) NOT NULL,
  strength DECIMAL(10, 4), -- Cluster density (higher = stronger)
  touch_count INTEGER DEFAULT 0,
  distance_pct DECIMAL(10, 4), -- Distance from current price as %

  -- Meta
  calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sr_levels_symbol ON support_resistance_levels(symbol, interval);
CREATE INDEX idx_sr_levels_type ON support_resistance_levels(level_type);

-- ============================================================================
-- ENTROPY READINGS (Shannon entropy filter)
-- ============================================================================
CREATE TABLE IF NOT EXISTS entropy_readings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol TEXT NOT NULL,
  interval TEXT NOT NULL,
  entropy_value DECIMAL(10, 6) NOT NULL,
  max_entropy DECIMAL(10, 6) NOT NULL,
  entropy_ratio DECIMAL(10, 6) NOT NULL, -- H / H_max
  is_tradable BOOLEAN NOT NULL, -- True if ratio < threshold
  window_size INTEGER NOT NULL,
  bins_used INTEGER NOT NULL,

  -- Meta
  measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT entropy_readings_unique UNIQUE (symbol, interval)
);

CREATE INDEX idx_entropy_symbol ON entropy_readings(symbol);

-- ============================================================================
-- BACKTEST RESULTS (VectorBT outputs)
-- ============================================================================
CREATE TABLE IF NOT EXISTS backtest_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy_id TEXT NOT NULL, -- e.g. 'sma_cross', 'rsi_reversal'
  symbol TEXT NOT NULL,
  interval TEXT NOT NULL,
  start_date TIMESTAMPTZ NOT NULL,
  end_date TIMESTAMPTZ NOT NULL,

  -- Parameters
  parameters JSONB NOT NULL DEFAULT '{}',

  -- Performance metrics
  total_return DECIMAL(10, 4),
  sharpe_ratio DECIMAL(10, 4),
  sortino_ratio DECIMAL(10, 4),
  calmar_ratio DECIMAL(10, 4),
  max_drawdown DECIMAL(10, 4),
  win_rate DECIMAL(10, 4),
  profit_factor DECIMAL(10, 4),
  expectancy DECIMAL(20, 8),
  total_trades INTEGER,
  avg_trade_duration TEXT,

  -- Equity curve (sampled to max 500 points)
  equity_curve JSONB,

  -- Fees/slippage used
  fees_pct DECIMAL(6, 4) DEFAULT 0.001,
  slippage_pct DECIMAL(6, 4) DEFAULT 0.0005,

  -- Meta
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_backtest_strategy ON backtest_results(strategy_id);
CREATE INDEX idx_backtest_symbol ON backtest_results(symbol);
CREATE INDEX idx_backtest_created ON backtest_results(created_at DESC);

-- ============================================================================
-- PERFORMANCE METRICS (Rolling metrics for live trading)
-- ============================================================================
CREATE TABLE IF NOT EXISTS performance_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  metric_type TEXT NOT NULL CHECK (metric_type IN ('rolling_30d', 'rolling_7d', 'all_time')),

  -- Portfolio-level metrics
  sharpe_ratio DECIMAL(10, 4),
  sortino_ratio DECIMAL(10, 4),
  calmar_ratio DECIMAL(10, 4),
  max_drawdown DECIMAL(10, 4),
  win_rate DECIMAL(10, 4),
  profit_factor DECIMAL(10, 4),
  expectancy DECIMAL(20, 8),
  kelly_fraction DECIMAL(10, 4),
  total_trades INTEGER,
  avg_win DECIMAL(20, 8),
  avg_loss DECIMAL(20, 8),

  -- Meta
  calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT performance_metrics_unique UNIQUE (metric_type)
);

-- ============================================================================
-- UPDATE RISK_EVENTS CONSTRAINT (add new quant event types)
-- ============================================================================

-- Drop the old constraint and add expanded one
ALTER TABLE risk_events DROP CONSTRAINT IF EXISTS risk_events_event_type_check;
ALTER TABLE risk_events ADD CONSTRAINT risk_events_event_type_check CHECK (
  event_type IN (
    -- Original types
    'limit_hit',
    'drawdown_alert',
    'daily_loss_limit',
    'position_size_limit',
    'margin_call',
    'max_positions',
    'price_spike',
    'connection_loss',
    'order_rejected',
    -- Proposal lifecycle
    'proposal_approved',
    'proposal_rejected',
    -- New quant engine types
    'entropy_gate_blocked',
    'regime_warning',
    'volatility_spike',
    'kelly_size_override',
    'backtest_validation_fail'
  )
);

-- ============================================================================
-- COMMENTS
-- ============================================================================
COMMENT ON TABLE klines_ohlcv IS 'OHLCV candlestick data from Binance for technical analysis';
COMMENT ON TABLE technical_indicators IS 'Calculated technical indicators per candle (SMA, RSI, MACD, etc.)';
COMMENT ON TABLE market_regimes IS 'Market regime classification (trending, ranging, volatile)';
COMMENT ON TABLE support_resistance_levels IS 'K-Means clustered support/resistance price levels';
COMMENT ON TABLE entropy_readings IS 'Shannon entropy readings for noise filtering';
COMMENT ON TABLE backtest_results IS 'VectorBT backtesting results and equity curves';
COMMENT ON TABLE performance_metrics IS 'Rolling performance metrics (Sharpe, Sortino, Kelly)';
