from pydantic_settings import BaseSettings
from typing import Optional


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

    # Risk Manager limits
    risk_max_position_size: float = 500.0
    risk_min_position_size: float = 10.0
    risk_max_daily_loss: float = 200.0
    risk_max_drawdown: float = 1000.0
    risk_max_open_positions: int = 3
    risk_max_positions_per_symbol: int = 1
    risk_min_account_balance: float = 1000.0
    risk_max_account_utilization: float = 0.8
    risk_auto_approval_threshold: float = 100.0

    # Quant Engine
    quant_enabled: bool = True
    quant_primary_interval: str = "1h"
    quant_symbols: str = "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT"
    entropy_window: int = 100
    entropy_bins: int = 10
    entropy_threshold_ratio: float = 0.75
    kelly_dampener: float = 0.35
    atr_multiplier: float = 2.5
    max_risk_per_trade_pct: float = 0.01
    quant_buy_notional_usd: float = 60.0
    kline_backfill_days: int = 30
    sr_clusters: int = 8
    sr_lookback: int = 500

    # ATR-based SL/TP (entry signals)
    sl_atr_multiplier: float = 1.5      # SL = entry - 1.5*ATR
    tp_atr_multiplier: float = 3.0      # TP = entry + 3.0*ATR → R:R = 1:2
    sl_fallback_pct: float = 0.03       # Fallback 3% si ATR no disponible
    tp_fallback_pct: float = 0.06       # Fallback 6%

    # Signal generator filters
    buy_entropy_max: float = 0.70       # Max entropy ratio para BUY
    buy_adx_min: float = 25.0           # ADX mínimo para BUY
    buy_regime_confidence_min: float = 60.0  # Confianza mínima de régimen para bloquear BUY

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}


settings = Settings()
