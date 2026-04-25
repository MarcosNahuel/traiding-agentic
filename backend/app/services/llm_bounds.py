"""Single source of truth for safe LLM-overrideable parameter bounds.

Post-mortem rationale: LLM config once produced buy_rsi_max=60, adx_min=12,
entropy=0.93, cooldown=30min — causing churn in noisy markets and -$18.74
across 49 trades. These bounds are the constitution the LLM cannot violate.
Any consumer (signal_generator, daily_strategist schema, etc.) MUST import
this dict instead of redefining the ranges.
"""

LLM_SAFE_BOUNDS = {
    "buy_rsi_max":             (30.0, 55.0),
    "buy_adx_min":             (18.0, 35.0),
    "buy_entropy_max":         (0.60, 0.80),
    "sell_rsi_min":            (60.0, 75.0),
    "signal_cooldown_minutes": (120, 360),
    "sl_atr_multiplier":       (0.5, 3.0),
    "tp_atr_multiplier":       (1.0, 4.0),
    "risk_multiplier":         (0.25, 2.0),
    "max_open_positions":      (1, 3),
}
