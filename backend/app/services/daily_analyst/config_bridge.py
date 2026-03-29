"""Config bridge: reads active LLM trading config from Supabase.

The signal generator calls load_active_config() every tick (60s).
Results are cached for 60s to minimize DB queries.
Falls back to None if no active config → signal generator uses settings defaults.
"""

import time
import logging
from typing import Optional

from .models import TradingConfigOverride

logger = logging.getLogger(__name__)

_config_cache: Optional[TradingConfigOverride] = None
_cache_ts: float = 0.0
_CACHE_TTL = 60.0  # seconds


def load_active_config() -> Optional[TradingConfigOverride]:
    """Load active LLM trading config from Supabase. Cached for 60s."""
    global _config_cache, _cache_ts

    if time.time() - _cache_ts < _CACHE_TTL:
        return _config_cache

    try:
        from ...db import get_supabase  # noqa: lazy import
        supabase = get_supabase()
        resp = (
            supabase.table("llm_trading_configs")
            .select("*")
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            row = resp.data[0]
            _config_cache = TradingConfigOverride(
                buy_adx_min=float(row.get("buy_adx_min") or 20.0),
                buy_entropy_max=float(row.get("buy_entropy_max") or 0.75),
                buy_rsi_max=float(row.get("buy_rsi_max") or 50.0),
                sell_rsi_min=float(row.get("sell_rsi_min") or 65.0),
                signal_cooldown_minutes=int(row.get("signal_cooldown_minutes") or 180),
                sl_atr_multiplier=float(row.get("sl_atr_multiplier") or 1.0),
                tp_atr_multiplier=float(row.get("tp_atr_multiplier") or 2.5),
                risk_multiplier=float(row.get("risk_multiplier") or 1.0),
                max_open_positions=int(row.get("max_open_positions") or 3),
                quant_symbols=row.get("quant_symbols") or "BTCUSDT,ETHUSDT,BNBUSDT",
                reasoning=row.get("reasoning") or "",
            )
            logger.info("Loaded active LLM config (adx=%s, entropy=%s, rsi=%s)",
                        _config_cache.buy_adx_min, _config_cache.buy_entropy_max,
                        _config_cache.buy_rsi_max)
        else:
            _config_cache = None
        _cache_ts = time.time()
    except Exception as e:
        logger.debug("LLM config load failed (using cache/defaults): %s", e)
        # Keep stale cache on failure rather than crashing

    return _config_cache


def invalidate_cache():
    """Force next load_active_config() to hit DB."""
    global _cache_ts
    _cache_ts = 0.0
