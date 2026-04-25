"""Single source of truth for LLM-overridable trading parameter bounds.

Used by:
- backend/app/services/signal_generator.py (runtime clamp)
- agents/daily_strategist/schemas.py (Pydantic Field constraints — Phase 1)

DO NOT redefine these bounds anywhere else. Import from here.

Post-mortem context: in 2026-03 the LLM analyst (Gemini Flash via LangGraph)
generated a config with cooldown=30min, RSI_max=60, ADX_min=12, entropy=0.93.
That config bypassed naive validation and produced -$18.74 in 49 trades by
trading in noisy non-trending markets. These bounds are the constitution.
"""

from typing import Final


LLM_SAFE_BOUNDS: Final[dict[str, tuple[float, float]]] = {
    "buy_rsi_max":             (30.0, 55.0),
    "buy_adx_min":             (18.0, 35.0),
    "buy_entropy_max":         (0.60, 0.80),
    "sell_rsi_min":            (60.0, 75.0),
    "signal_cooldown_minutes": (120.0, 360.0),
    "sl_atr_multiplier":       (0.5, 3.0),
    "tp_atr_multiplier":       (1.0, 4.0),
    "risk_multiplier":         (0.25, 2.0),
    "max_open_positions":      (1.0, 3.0),
}


def clamp(key: str, value: float) -> float:
    """Clamp a value to its safe bound. Raises KeyError if key unknown."""
    lo, hi = LLM_SAFE_BOUNDS[key]
    return max(lo, min(hi, value))


def is_within_bounds(key: str, value: float) -> bool:
    """Check if a value is within bounds without clamping."""
    if key not in LLM_SAFE_BOUNDS:
        return False
    lo, hi = LLM_SAFE_BOUNDS[key]
    return lo <= value <= hi
