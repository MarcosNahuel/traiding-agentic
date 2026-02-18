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

    # Security - shared secret for Next.js → Python calls
    backend_secret: str = "trading-backend-secret"

    # Telegram Notifications (optional)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Quant Engine
    quant_enabled: bool = True
    quant_primary_interval: str = "1h"
    quant_symbols: str = "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT"
    entropy_window: int = 100
    entropy_bins: int = 10
    entropy_threshold_ratio: float = 0.85
    kelly_dampener: float = 0.5
    atr_multiplier: float = 2.0
    max_risk_per_trade_pct: float = 0.02
    kline_backfill_days: int = 30
    sr_clusters: int = 8
    sr_lookback: int = 500

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}


settings = Settings()
