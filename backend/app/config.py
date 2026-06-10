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
    "BTCUSDT": 1.0,   # más tight (default 1.2)
}
SYMBOL_TP_ATR_OVERRIDES: dict[str, float] = {
    "BTCUSDT": 1.5,   # más alcanzable (default 2.0)
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
    kline_backfill_days: int = 45       # ERA 30 — bull filter necesita 744 velas 1h (~31 días)
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

    # ── Estrategia de entrada (backtest lab 2026-06-10, 24 meses BTC+ETH 1h) ──
    # "legacy": trend-momentum actual — PF 0.50 en backtest, pierde estructuralmente
    #           (compra debilidad RSI<50 con SL ajustado; los costos se comen el edge).
    # "donchian_breakout": breakout máximo 55 velas + master switch alcista +
    #           chandelier 3×ATR — PF 1.30 robusto en ambas mitades del período
    #           (1.29/1.31), 155 trades, expectancy +$0.19/trade, max DD $19.
    # Evidencia: scripts/backtest-lab/results/ + docs/knowledge-base/evaluations/2026-06-10.
    entry_strategy: str = "donchian_breakout"
    donchian_entry_bars: int = 55       # canal Donchian (sensibilidad: 40/55/70 todos PF>1)

    # Master switch macro: solo abrir LONGs si close > SMA(bull_sma_bars) y la SMA sube.
    # En bear/chop el bot queda en cash — TODA variante long-only pierde en bear (lab R2/R3).
    bull_filter_enabled: bool = True
    bull_sma_bars: int = 720            # 30 días en velas 1h — SMA600 degrada PF 1.30→1.06 (lab R5)
    bull_slope_bars: int = 24           # pendiente: SMA hoy > SMA hace 24 velas

    # Exits donchian: SL inicial 2×ATR, TP lejano (el exit real es el trailing chandelier)
    donchian_sl_atr_mult: float = 2.0
    donchian_tp_max_pct: float = 0.15   # cap de TP para donchian (legacy mantiene 7%)
    trail_mode: str = "chandelier_pure" # "legacy" = progress-gated (solo si entry_strategy=legacy)
    trail_chandelier_mult: float = 3.0  # ERA 2.0 — lab: trailing apretado corta winners

    # LLM Daily Analyst (LangGraph + Gemini)
    google_ai_api_key: str = ""            # Gemini API key (GOOGLE_AI_API_KEY en .env)
    analyst_model_name: str = "gemini-3.1-flash-lite-preview"
    analyst_enabled: bool = True           # Daily LLM analyst activo (03:00-04:30 UTC)

    # Claude Veto Co-Pilot (hot-path BUY gate) — ver docs/superpowers/specs/2026-05-30-claude-veto-copilot-design.md
    copilot_enabled: bool = False          # Kill switch — default off; bot opera idéntico a hoy
    # Smoke 2026-05-30: el agente tarda ~45-50s (cold-start del CLI + round-trips de tools,
    # NO del modelo — Haiku≈Sonnet). 20s garantizaba fail-open siempre. 60s deja vetar de verdad.
    copilot_timeout_s: float = 60.0        # Hard timeout → fail-open (ejecuta como hoy)
    copilot_max_turns: int = 8             # Bound del tool loop del agente
    copilot_model: str = ""                # "" = default del SDK; override opcional (ej. claude-sonnet-4-6)
    copilot_kb_dir: str = ""               # "" = ruta repo docs/knowledge-base; en deploy: bind-mount + COPILOT_KB_DIR
    claude_code_oauth_token: str = ""      # Auth plan Claude Max (claude setup-token)

    # Daily Strategist Agent (fleet data+knowledge->decision; corre off hot-path 1x/día)
    strategist_enabled: bool = False
    strategist_timeout_s: float = 240.0    # fleet con subagentes tarda más; corre off hot-path
    strategist_max_turns: int = 40
    strategist_max_budget_usd: float = 1.5  # cap nativo del SDK (spec: <$1.50/día)
    strategist_decision_model: str = "claude-sonnet-4-6"   # decisor en Sonnet (sin Haiku)
    strategist_data_model: str = ""        # "" = Sonnet (default abajo); subagente data-analyst
    strategist_data_effort: str = "low"    # Sonnet low-effort para juntar datos (rápido/barato)
    strategist_knowledge_model: str = ""   # "" = sonnet; subagente knowledge
    strategist_approval_token: str = ""    # token para aprobar/rechazar propuestas vía link de Telegram
    bot_public_url: str = "http://trading-backend.145.223.95.154.sslip.io"  # base para los links de aprobación

    # Telegram conversacional — le escribís al bot y el agente Claude (read-only) responde
    chat_enabled: bool = False             # gating: requiere Node+CLI en la imagen + OAuth token
    chat_timeout_s: float = 150.0          # el agente usa tools; puede tardar
    chat_max_turns: int = 12
    telegram_webhook_secret: str = ""      # X-Telegram-Bot-Api-Secret-Token para validar el webhook

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}


settings = Settings()
