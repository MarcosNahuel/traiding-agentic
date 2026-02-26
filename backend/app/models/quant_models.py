"""Pydantic models for the quantitative analysis engine."""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============================================================================
# KLINES
# ============================================================================

class KlineData(BaseModel):
    symbol: str
    interval: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: Optional[float] = None
    trades_count: Optional[int] = None
    taker_buy_base_volume: Optional[float] = None
    taker_buy_quote_volume: Optional[float] = None


class KlineStatusItem(BaseModel):
    symbol: str
    interval: str
    latest_open_time: Optional[str] = None
    count: int = 0


# ============================================================================
# TECHNICAL INDICATORS
# ============================================================================

class TechnicalIndicators(BaseModel):
    symbol: str
    interval: str
    candle_time: datetime

    # Trend
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    ema_50: Optional[float] = None

    # Momentum
    rsi_14: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    adx_14: Optional[float] = None

    # Volatility
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_bandwidth: Optional[float] = None
    atr_14: Optional[float] = None

    # Volume
    obv: Optional[float] = None
    vwap: Optional[float] = None


# ============================================================================
# ENTROPY
# ============================================================================

class EntropyReading(BaseModel):
    symbol: str
    interval: str
    entropy_value: float
    max_entropy: float
    entropy_ratio: float
    is_tradable: bool
    window_size: int
    bins_used: int
    measured_at: Optional[datetime] = None


# ============================================================================
# SUPPORT / RESISTANCE
# ============================================================================

class SRLevel(BaseModel):
    level_type: str  # "support" or "resistance"
    price_level: float
    strength: float
    touch_count: int = 0
    distance_pct: float = 0.0


class SRLevelsResult(BaseModel):
    symbol: str
    interval: str
    current_price: float
    levels: List[SRLevel]
    calculated_at: Optional[datetime] = None


# ============================================================================
# MARKET REGIME
# ============================================================================

class MarketRegime(BaseModel):
    symbol: str
    interval: str
    regime: str  # trending_up, trending_down, ranging, volatile, low_liquidity
    confidence: float
    adx_value: Optional[float] = None
    bb_bandwidth: Optional[float] = None
    atr_close_ratio: Optional[float] = None
    hurst_exponent: Optional[float] = None
    detected_at: Optional[datetime] = None


# ============================================================================
# POSITION SIZING
# ============================================================================

class PositionSizing(BaseModel):
    symbol: str
    kelly_fraction: Optional[float] = None
    kelly_size_usd: Optional[float] = None
    atr_size_usd: Optional[float] = None
    recommended_size_usd: float
    method: str  # "kelly_atr", "atr_only", "fixed_pct"
    details: Dict[str, Any] = {}


# ============================================================================
# QUANT SNAPSHOT (full analysis for LLM)
# ============================================================================

class QuantSnapshot(BaseModel):
    symbol: str
    timestamp: datetime
    indicators: Optional[TechnicalIndicators] = None
    entropy: Optional[EntropyReading] = None
    regime: Optional[MarketRegime] = None
    sr_levels: Optional[SRLevelsResult] = None
    position_sizing: Optional[PositionSizing] = None
    is_tradable: bool = True
    trade_blocks: List[str] = []


# ============================================================================
# BACKTEST
# ============================================================================

class BacktestRequest(BaseModel):
    strategy_id: str  # e.g. "sma_cross", "rsi_reversal", "bbands_squeeze", "trend_momentum_v2"
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    lookback_days: int = 30
    parameters: Dict[str, Any] = {}


class BacktestBenchmarkRequest(BaseModel):
    symbol: str = "BTCUSDT"
    market: str = "spot"  # spot | futures
    horizon: str = "intraday"  # scalping | intraday | swing
    lookback_days: int = 30
    store_results: bool = True
    interval_override: Optional[str] = None


class BacktestResult(BaseModel):
    id: Optional[str] = None
    strategy_id: str
    symbol: str
    interval: str
    start_date: datetime
    end_date: datetime
    parameters: Dict[str, Any] = {}
    total_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    calmar_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    expectancy: Optional[float] = None
    total_trades: Optional[int] = None
    avg_trade_duration: Optional[str] = None
    equity_curve: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[datetime] = None


# ============================================================================
# PERFORMANCE METRICS
# ============================================================================

class PerformanceMetrics(BaseModel):
    metric_type: str  # "rolling_30d", "rolling_7d", "all_time"
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    calmar_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    expectancy: Optional[float] = None
    kelly_fraction: Optional[float] = None
    total_trades: Optional[int] = None
    avg_win: Optional[float] = None
    avg_loss: Optional[float] = None
    calculated_at: Optional[datetime] = None


# ============================================================================
# QUANT ENGINE STATUS
# ============================================================================

class QuantEngineStatus(BaseModel):
    enabled: bool
    tick_count: int = 0
    last_tick_at: Optional[datetime] = None
    symbols: List[str] = []
    primary_interval: str = "1h"
    modules: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []
