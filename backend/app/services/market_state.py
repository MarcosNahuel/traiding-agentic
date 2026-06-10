"""Market state: master switch macro alcista/bajista.

Backtest lab 2026-06-10 (24 meses BTC+ETH, scripts/backtest-lab/):
TODA estrategia long-only spot pierde en mercado bajista — la única defensa
es no operar. Este filtro mantiene al bot en cash salvo que:
  1. close > SMA(bull_sma_bars)         (precio arriba de la media de ~25 días)
  2. SMA hoy > SMA hace bull_slope_bars (la media está subiendo)

Fail-closed: si no hay velas suficientes para computar la SMA, NO es bull
(mejor perder una entrada que operar a ciegas).
"""

import logging
from typing import Optional

from ..config import settings
from .technical_analysis import _load_klines_df

logger = logging.getLogger(__name__)


def is_bull_market(symbol: str, interval: str = "1h") -> Optional[bool]:
    """True si el régimen macro es alcista, False si no, None si faltan datos.

    El caller debe tratar None como False (fail-closed) para gating de BUYs.
    """
    needed = settings.bull_sma_bars + settings.bull_slope_bars
    df = _load_klines_df(symbol, interval, limit=needed + 10)
    if df is None or len(df) < needed:
        logger.warning(
            "Bull filter [%s]: datos insuficientes (%s velas, necesita %d) — fail-closed",
            symbol, len(df) if df is not None else 0, needed,
        )
        return None

    closes = df["close"].astype(float)
    sma = closes.rolling(settings.bull_sma_bars).mean()
    sma_now = sma.iloc[-1]
    sma_prev = sma.iloc[-1 - settings.bull_slope_bars]
    close_now = closes.iloc[-1]

    bull = bool(close_now > sma_now and sma_now > sma_prev)
    logger.debug(
        "Bull filter [%s]: close=%.2f sma=%.2f sma_prev=%.2f → %s",
        symbol, close_now, sma_now, sma_prev, "BULL" if bull else "BEAR/CHOP",
    )
    return bull


def donchian_breakout_level(symbol: str, interval: str = "1h") -> Optional[float]:
    """Máximo de las últimas `donchian_entry_bars` velas CERRADAS.

    Una entrada donchian se dispara cuando el precio actual supera este nivel.
    None si faltan datos.

    IMPORTANTE: el kline_collector upserta también la vela 1h EN FORMACIÓN.
    Si esa vela entrara al canal, el precio actual nunca superaría su propio
    high y el breakout no dispararía jamás. La excluimos por timestamp.
    """
    bars = settings.donchian_entry_bars
    df = _load_klines_df(symbol, interval, limit=bars + 5)
    if df is None or len(df) < bars:
        return None

    # Excluir la vela aún abierta (open_time + intervalo > ahora)
    try:
        from datetime import datetime, timezone, timedelta

        interval_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
        mins = interval_minutes.get(interval, 60)
        last_open = df.index[-1]
        if last_open.tzinfo is None:
            last_open = last_open.tz_localize("UTC")
        if last_open + timedelta(minutes=mins) > datetime.now(timezone.utc):
            df = df.iloc[:-1]
    except Exception:
        df = df.iloc[:-1]  # ante la duda, descartar la última (conservador)

    if len(df) < bars:
        return None
    return float(df["high"].astype(float).iloc[-bars:].max())
