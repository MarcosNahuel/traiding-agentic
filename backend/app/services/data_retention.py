"""Data retention service — limpieza periódica de tablas de alto volumen.

Tablas y políticas:
  - reconciliation_runs: 7 días (corre cada 60s → 1,440 rows/día)
  - klines_ohlcv:        1m=7d, 5m=14d, 15m=30d, 1h=90d, 4h/1d=180d
  - technical_indicators: 30 días
  - risk_events:          90 días (solo resolved=true)
  - trade_proposals:      30 días (solo rejected/dead_letter/draft/cancelled)
  - klines de símbolos inactivos (SOLUSDT, XRPUSDT, BNBUSDT): borrar todo
"""

import logging
from datetime import datetime, timezone

from ..db import get_supabase

logger = logging.getLogger(__name__)

_last_retention_date: str | None = None


def should_run_retention(now: datetime) -> bool:
    """True si son las 02:00-02:01 UTC y no se ejecutó hoy."""
    global _last_retention_date
    today = now.strftime("%Y-%m-%d")
    return now.hour == 2 and now.minute < 2 and _last_retention_date != today


async def run_data_retention() -> dict:
    """Llama la función RPC de retención en Supabase y retorna el resumen."""
    global _last_retention_date
    try:
        supabase = get_supabase()
        result = supabase.rpc("run_data_retention").execute()
        summary = result.data or {}
        logger.info("Data retention complete: %s", summary)
        _last_retention_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return summary
    except Exception as e:
        logger.error("Data retention failed: %s", e)
        return {}
