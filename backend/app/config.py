from pydantic_settings import BaseSettings
from typing import Optional


# ── Per-symbol overrides (2026-04-11 analysis) ──
# Rationale: BTC post-fix está en break-even noise (6 trades, PnL microscópico).
# ETH post-fix está ganando consistentemente (WR 86%, R+0.84).
# Estos dicts permiten tune por símbolo sin romper defaults.
#
# SL/TP multipliers en ATR units:
#   - BTC: volatilidad menor, SL/TP más tight para capturar moves modestos
#   - ETH: más volátil, defaults funcionan bien
SYMBOL_SL_ATR_OVERRIDES: dict[str, float] = {
    "BTCUSDT": 1.0,
    "ETHUSDT": 0.9,   # 2026-04-27: tighter SL (avg loss -2.75% > avg win +1.67% → R:R 0.61)
}
SYMBOL_TP_ATR_OVERRIDES: dict[str, float] = {
    "BTCUSDT": 1.5,
}

# Position size USD por símbolo (edge-based sizing).
# 2026-04-21 reassessment: ETH WR cayó de 86% → 78% en muestra mayor,
# losers de -$1.65/-$1.41 con notional $100 duelen. Bajamos a $80 hasta
# recuperar WR >80% estable en >20 trades.
SYMBOL_NOTIONAL_OVERRIDES: dict[str, float] = {
    "ETHUSDT": 80.0,
}


def get_symbol_sl_atr(symbol: str, default: float) -> float:
    return SYMBOL_SL_ATR_OVERRIDES.get(symbol, default)


def get_symbol_tp_atr(symbol: str, default: float) -> float:
    return SYMBOL_TP_ATR_OVERRIDES.get(symbol, default)


def get_symbol_notional(symbol: str, default: float) -> float:
    return SYMBOL_NOTIONAL_OVERRIDES.get(symbol, default)


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # Binance Proxy
    binance_proxy_url: str = "https://binance.italicia.com"
    binance_proxy_auth_secret: str = ""
    binance_testnet_api_key: str = ""
    binance_testnet_secret: str = ""
    binance_env: str = "testnet"

    # Backend
    port: int = 8000
    node_env: str = "production"

    # Kill Switch — set to True to enable trade execution
    trading_enabled: bool = False

    # Security - shared secret for Next.js → Python calls (MUST be set via env)
    backend_secret: str = ""

    # Telegram Notifications (optional)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = False    # Kill switch — set to True to allow notifications

    # Risk Manager limits
    risk_max_position_size: float = 500.0
    risk_min_position_size: float = 10.0
    risk_max_daily_loss: float = 200.0
    risk_max_drawdown: float = 1000.0
    risk_max_open_positions: int = 3          # Revertido: max 3 posiciones simultáneas
    risk_max_positions_per_symbol: int = 1
    risk_min_account_balance: float = 1000.0
    risk_max_account_utilization: float = 0.8
    risk_auto_approval_threshold: float = 100.0

    # Quant Engine
    quant_enabled: bool = True
    quant_primary_interval: str = "1h"
    # 2026-04-21: BTC pausado — 7d WR 50%, P&L +$0.19 (breakeven noise).
    # Re-enable una vez confirmado edge en 2+ semanas. ETH es el único
    # símbolo con edge claro post-mortem.
    quant_symbols: str = "ETHUSDT"
    entropy_window: int = 100
    entropy_bins: int = 10
    entropy_threshold_ratio: float = 0.75       # Revertido: filtrar mercados ruidosos
    kelly_dampener: float = 0.35
    atr_multiplier: float = 2.5
    max_risk_per_trade_pct: float = 0.01
    quant_buy_notional_usd: float = 60.0
    kline_backfill_days: int = 30
    sr_clusters: int = 8
    sr_lookback: int = 500

    # ATR-based SL/TP — con caps porcentuales en executor.py (SL max 3%, TP max 7%)
    sl_atr_multiplier: float = 1.2      # ERA 1.0 — ligeramente más holgura para evitar SL por ruido
    tp_atr_multiplier: float = 2.0      # ERA 2.5 — TP más alcanzable (solo 1/49 trades tocó TP antes)
    sl_fallback_pct: float = 0.02       # Fallback 2%
    tp_fallback_pct: float = 0.04       # ERA 0.05 — fallback 4% (más cercano, más alcanzable)

    # Signal generator filters — AGGRESSIVE TESTING MODE
    buy_entropy_max: float = 0.75       # Revertido: filtrar señales en mercados ruidosos
    buy_adx_min: float = 20.0           # ERA 15.0 — filtrar señales sin trend mínimo
    buy_regime_confidence_min: float = 85.0  # Testnet: solo bloquea downtrends muy fuertes (>85%)

    # LLM Daily Analyst (LangGraph + Gemini)
    google_ai_api_key: str = ""            # Gemini API key (GOOGLE_AI_API_KEY en .env)
    analyst_model_name: str = "gemini-3.1-flash-lite-preview"
    analyst_enabled: bool = True           # Daily LLM analyst activo (03:00-04:30 UTC)

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}


settings = Settings()
