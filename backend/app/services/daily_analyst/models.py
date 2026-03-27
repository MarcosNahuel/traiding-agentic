"""Pydantic models for the Daily LLM Analyst.

TradingConfigOverride: LLM output that configures the deterministic engine.
All fields have hard bounds — the LLM cannot set values outside these ranges.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class TradingConfigOverride(BaseModel):
    """Parameters the LLM can adjust for the next trading session.

    Hard bounds enforced via Pydantic Field constraints.
    validate_bounds() clamps any out-of-range values as a second safety net.
    """
    buy_adx_min: float = Field(default=20.0, ge=10.0, le=40.0,
        description="Minimum ADX for BUY signals (higher = stronger trend required)")
    buy_entropy_max: float = Field(default=0.85, ge=0.50, le=0.95,
        description="Maximum entropy ratio for BUY (lower = less noise tolerance)")
    buy_rsi_max: float = Field(default=50.0, ge=30.0, le=65.0,
        description="Maximum RSI for BUY entry (lower = more oversold required)")
    sell_rsi_min: float = Field(default=65.0, ge=55.0, le=80.0,
        description="Minimum RSI for SELL exit (higher = more overbought required)")
    signal_cooldown_minutes: int = Field(default=180, ge=30, le=480,
        description="Minutes between signals for same symbol")
    sl_atr_multiplier: float = Field(default=1.0, ge=0.5, le=3.0,
        description="Stop-loss = entry - (multiplier × ATR)")
    tp_atr_multiplier: float = Field(default=1.5, ge=0.8, le=4.0,
        description="Take-profit = entry + (multiplier × ATR)")
    risk_multiplier: float = Field(default=1.0, ge=0.25, le=2.0,
        description="Position size multiplier (0.5 = half size, 2.0 = double)")
    max_open_positions: int = Field(default=5, ge=1, le=8,
        description="Maximum simultaneous open positions")
    quant_symbols: str = Field(default="BTCUSDT,ETHUSDT,BNBUSDT",
        description="Comma-separated symbols to trade")
    reasoning: str = Field(default="",
        description="LLM explanation for the adjustments")


# Hard bounds for validate_bounds() clamping
PARAM_BOUNDS = {
    "buy_adx_min": (10.0, 40.0),
    "buy_entropy_max": (0.50, 0.95),
    "buy_rsi_max": (30.0, 65.0),
    "sell_rsi_min": (55.0, 80.0),
    "signal_cooldown_minutes": (30, 480),
    "sl_atr_multiplier": (0.5, 3.0),
    "tp_atr_multiplier": (0.8, 4.0),
    "risk_multiplier": (0.25, 2.0),
    "max_open_positions": (1, 8),
}


def validate_bounds(config: dict) -> tuple[dict, list[str]]:
    """Clamp config values to hard bounds. Returns (clamped_config, warnings)."""
    clamped = dict(config)
    warnings = []
    for key, (lo, hi) in PARAM_BOUNDS.items():
        if key in clamped and clamped[key] is not None:
            val = clamped[key]
            if val < lo:
                warnings.append(f"{key}: {val} clamped to min {lo}")
                clamped[key] = lo
            elif val > hi:
                warnings.append(f"{key}: {val} clamped to max {hi}")
                clamped[key] = hi
    return clamped, warnings


class SymbolAnalysis(BaseModel):
    symbol: str
    trend: str  # "bullish", "bearish", "neutral"
    regime: str  # from regime_detector
    tradability_score: float = Field(ge=0.0, le=1.0)
    notes: str = ""


class DailyBrief(BaseModel):
    brief_date: str
    market_summary: str
    symbol_analyses: List[SymbolAnalysis]
    risk_assessment: str
    fear_greed_value: Optional[int] = None
    fear_greed_label: Optional[str] = None
    news_summary: str = ""
    config_overrides: TradingConfigOverride
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)


class TradeReview(BaseModel):
    trade_id: str
    symbol: str
    side: str
    pnl: float
    pnl_percent: float
    analysis: str
    was_correct_call: bool


class AuditReport(BaseModel):
    audit_date: str
    performance_summary: Dict[str, Any]
    trade_reviews: List[TradeReview]
    error_analysis: str = ""
    market_events: str = ""
    recommendations: List[str] = []
    overall_grade: str = "C"  # A-F
    next_day_adjustments: Optional[TradingConfigOverride] = None
