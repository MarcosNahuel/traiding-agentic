"""Strategy Replay Simulator — Fast-forward histórico del bot completo.

Replica EXACTAMENTE la lógica del signal_generator + trading_loop contra
data histórica. Corre meses de trading en segundos.

Modos:
  - "rules": Solo reglas técnicas (RSI, MACD, ADX, SMA, Regime, Entropy)
  - "ml": Solo señales ML (LightGBM logret predictions)
  - "hybrid": Reglas técnicas + ML como confirmación

Uso:
    from app.services.strategy_replay import run_replay
    result = await run_replay("BTCUSDT", mode="rules", days=90)
    print(result["summary"])
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
import pandas_ta_classic as ta

from ..config import settings
from ..db import get_supabase

logger = logging.getLogger(__name__)

# ── Constantes ──────────────────────────────────────────────────────
FEES_PCT = 0.001        # 0.1% por trade (maker/taker promedio)
SLIPPAGE_PCT = 0.0005   # 0.05% slippage simulado
MIN_BARS_WARMUP = 60    # Velas mínimas para indicadores
COOLDOWN_BARS = 3       # 3h cooldown entre señales (3 barras de 1h)


# ── Modelos ─────────────────────────────────────────────────────────
@dataclass
class Position:
    symbol: str
    entry_price: float
    entry_bar: int
    quantity: float
    sl_price: float
    tp_price: float
    highest_since_entry: float = 0.0

    def __post_init__(self):
        self.highest_since_entry = self.entry_price


@dataclass
class ClosedTrade:
    symbol: str
    entry_price: float
    exit_price: float
    entry_bar: int
    exit_bar: int
    pnl: float
    pnl_pct: float
    exit_reason: str  # "sl", "tp", "signal", "time_stop", "trailing", "ml_exit"
    hold_bars: int = 0

    def __post_init__(self):
        self.hold_bars = self.exit_bar - self.entry_bar


@dataclass
class ReplayResult:
    symbol: str
    mode: str
    total_bars: int
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    avg_pnl_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_hold_bars: float = 0.0
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)
    signals_generated: int = 0
    signals_blocked: int = 0


# ── Funciones auxiliares ────────────────────────────────────────────
def _hurst_exponent(prices: np.ndarray, max_lag: int = 20) -> float:
    """Hurst exponent via R/S analysis."""
    if len(prices) < max_lag * 2:
        return 0.5
    lags = range(2, max_lag + 1)
    rs_values = []
    for lag in lags:
        sub_series = [prices[i:i + lag] for i in range(0, len(prices) - lag + 1, lag)]
        sub_series = [s for s in sub_series if len(s) == lag]
        if not sub_series:
            continue
        rs_list = []
        for ss in sub_series:
            mean_s = np.mean(ss)
            dev = np.cumsum(ss - mean_s)
            r = np.max(dev) - np.min(dev)
            s = np.std(ss, ddof=1)
            if s > 0:
                rs_list.append(r / s)
        if rs_list:
            rs_values.append((np.log(lag), np.log(np.mean(rs_list))))
    if len(rs_values) < 3:
        return 0.5
    x = np.array([v[0] for v in rs_values])
    y = np.array([v[1] for v in rs_values])
    slope, _ = np.polyfit(x, y, 1)
    return float(np.clip(slope, 0.0, 1.0))


def _compute_entropy(closes: np.ndarray, window: int = 100, bins: int = 10) -> float:
    """Shannon entropy ratio de log-returns."""
    if len(closes) < window:
        return 0.7  # default
    log_rets = np.diff(np.log(closes[-window:]))
    log_rets = log_rets[~np.isnan(log_rets)]
    if len(log_rets) < 20:
        return 0.7
    counts, _ = np.histogram(log_rets, bins=bins)
    total = counts.sum()
    if total == 0:
        return 0.7
    probs = counts / total
    probs = probs[probs > 0]
    h = -np.sum(probs * np.log2(probs))
    h_max = math.log2(bins)
    return h / h_max if h_max > 0 else 0.7


def _detect_regime(
    adx: float, bb_bw: float, atr_ratio: float, hurst: float,
    close: float, sma_20: float, volume_recent: float, volume_avg: float,
) -> tuple[str, float]:
    """Detectar régimen de mercado (replica regime_detector.py)."""
    regime = "ranging"
    confidence = 50.0

    if adx > 40 and hurst > 0.6:
        if close > sma_20:
            regime, confidence = "trending_up", min(90.0, 50 + adx)
        else:
            regime, confidence = "trending_down", min(90.0, 50 + adx)
    elif adx > 25 and hurst > 0.55:
        if close > sma_20:
            regime, confidence = "trending_up", min(75.0, 40 + adx)
        else:
            regime, confidence = "trending_down", min(75.0, 40 + adx)
    elif bb_bw > 0.08 or atr_ratio > 0.04:
        regime, confidence = "volatile", min(85.0, 50 + bb_bw * 200)
    elif adx < 20 and 0.4 < hurst < 0.6:
        regime, confidence = "ranging", min(80.0, 60 + (20 - adx))
    elif volume_avg > 0 and volume_recent < volume_avg * 0.3:
        regime, confidence = "low_liquidity", 60.0

    return regime, confidence


def _compute_sl_tp(price: float, atr: float) -> tuple[float, float]:
    """Calcular SL/TP usando ATR (replica executor._compute_sl_tp)."""
    sl_mult = settings.sl_atr_multiplier
    tp_mult = settings.tp_atr_multiplier
    sl_fb = settings.sl_fallback_pct
    tp_fb = settings.tp_fallback_pct

    if atr > 0 and (atr / price) <= 0.25:
        sl = round(price - sl_mult * atr, 2)
        tp = round(price + tp_mult * atr, 2)
    else:
        sl = round(price * (1 - sl_fb), 2)
        tp = round(price * (1 + tp_fb), 2)
    return sl, tp


def _apply_fees(entry: float, exit_price: float) -> float:
    """PnL neto después de fees + slippage."""
    cost = FEES_PCT * 2 + SLIPPAGE_PCT * 2  # entry + exit
    gross_pnl_pct = (exit_price - entry) / entry
    return gross_pnl_pct - cost


# ── Carga de datos ──────────────────────────────────────────────────
async def _load_klines(symbol: str, interval: str = "1h", days: int = 365) -> pd.DataFrame:
    """Cargar klines históricas de Supabase."""
    supabase = get_supabase()
    limit = days * 24 if interval == "1h" else days * 24 * 60

    # Paginar: Supabase tiene límite de 1000 por request
    all_data = []
    offset = 0
    page_size = 1000

    while True:
        resp = (
            supabase.table("klines_ohlcv")
            .select("open_time, open, high, low, close, volume, quote_volume")
            .eq("symbol", symbol)
            .eq("interval", interval)
            .order("open_time", desc=False)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not resp.data:
            break
        all_data.extend(resp.data)
        if len(resp.data) < page_size:
            break
        offset += page_size

    if not all_data:
        raise ValueError(f"No klines data for {symbol} {interval}")

    df = pd.DataFrame(all_data)
    for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["open_time"] = pd.to_datetime(df["open_time"])
    df.set_index("open_time", inplace=True)
    df.sort_index(inplace=True)

    # Limitar a los últimos N días
    if days and len(df) > days * 24:
        df = df.iloc[-(days * 24):]

    logger.info("Loaded %d klines for %s %s (%s → %s)",
                len(df), symbol, interval,
                df.index[0].strftime("%Y-%m-%d"),
                df.index[-1].strftime("%Y-%m-%d"))
    return df


# ── Indicadores incrementales ───────────────────────────────────────
def _compute_indicators_at(df: pd.DataFrame, i: int) -> Optional[dict]:
    """Computar indicadores técnicos en la barra i usando datos [0:i+1].

    Usa solo datos pasados (sin look-ahead bias).
    """
    if i < MIN_BARS_WARMUP:
        return None

    window = df.iloc[max(0, i - 250):i + 1]  # Ventana de 250 barras max
    close = window["close"]
    high = window["high"]
    low = window["low"]
    volume = window["volume"]

    try:
        sma_20 = ta.sma(close, length=20)
        sma_50 = ta.sma(close, length=50)
        rsi_14 = ta.rsi(close, length=14)
        adx_df = ta.adx(high, low, close, length=14)
        atr_14 = ta.atr(high, low, close, length=14)
        macd = ta.macd(close, fast=12, slow=26, signal=9)
        bb = ta.bbands(close, length=20, std=2)
        vol_ma = ta.sma(volume, length=20)

        # Extraer últimos valores
        adx_col = [c for c in adx_df.columns if c.startswith("ADX")] if adx_df is not None else []
        adx_val = float(adx_df[adx_col[0]].iloc[-1]) if adx_col and adx_df is not None else 0.0

        bb_upper = float(bb[[c for c in bb.columns if "BBU" in c][0]].iloc[-1]) if bb is not None else 0
        bb_lower = float(bb[[c for c in bb.columns if "BBL" in c][0]].iloc[-1]) if bb is not None else 0
        bb_mid = float(bb[[c for c in bb.columns if "BBM" in c][0]].iloc[-1]) if bb is not None else 0
        bb_bw = (bb_upper - bb_lower) / bb_mid if bb_mid > 0 else 0.0

        macd_hist_val = 0.0
        if macd is not None:
            hist_col = [c for c in macd.columns if "h" in c.lower() or "hist" in c.lower()]
            if hist_col:
                macd_hist_val = float(macd[hist_col[0]].iloc[-1])

        ppo_val = 0.0
        if sma_50 is not None and float(sma_50.iloc[-1]) > 0:
            ema12 = ta.ema(close, length=12)
            ema26 = ta.ema(close, length=26)
            if ema12 is not None and ema26 is not None:
                ppo_val = ((float(ema12.iloc[-1]) - float(ema26.iloc[-1])) / float(ema26.iloc[-1])) * 100

        vol_ratio = None
        if vol_ma is not None and float(vol_ma.iloc[-1]) > 0:
            vol_ratio = float(volume.iloc[-1]) / float(vol_ma.iloc[-1])

        return {
            "close": float(close.iloc[-1]),
            "high": float(high.iloc[-1]),
            "low": float(low.iloc[-1]),
            "sma_20": float(sma_20.iloc[-1]) if sma_20 is not None else None,
            "sma_50": float(sma_50.iloc[-1]) if sma_50 is not None else None,
            "rsi_14": float(rsi_14.iloc[-1]) if rsi_14 is not None else None,
            "adx_14": adx_val,
            "atr_14": float(atr_14.iloc[-1]) if atr_14 is not None else None,
            "macd_histogram": macd_hist_val,
            "bb_bandwidth": bb_bw,
            "volume_ratio": vol_ratio,
            "ppo": ppo_val,
        }
    except Exception as e:
        logger.debug("Indicator error at bar %d: %s", i, e)
        return None


# ── Motor de Replay ─────────────────────────────────────────────────
async def run_replay(
    symbol: str,
    mode: str = "rules",
    days: int = 90,
    interval: str = "1h",
    ml_model=None,
    ml_features_df: pd.DataFrame | None = None,
    max_positions: int | None = None,
) -> ReplayResult:
    """Ejecutar replay completo de la estrategia.

    Args:
        symbol: Par de trading (BTCUSDT, ETHUSDT, etc.)
        mode: "rules" | "ml" | "hybrid"
        days: Días de historia a simular
        interval: Intervalo de velas
        ml_model: Modelo LightGBM cargado (para mode=ml/hybrid)
        ml_features_df: DataFrame con features ML pre-computadas
        max_positions: Override de max posiciones (default: settings)

    Returns:
        ReplayResult con métricas y equity curve
    """
    df = await _load_klines(symbol, interval, days)
    max_pos = max_positions or settings.risk_max_open_positions

    # Config thresholds (mismos que signal_generator)
    buy_rsi_max = 50.0
    buy_adx_min = settings.buy_adx_min
    buy_entropy_max = settings.buy_entropy_max
    buy_regime_conf_min = settings.buy_regime_confidence_min
    sell_rsi_min = 65.0
    sell_macd_hist_max = 5.0
    buy_macd_hist_min = -10.0
    time_stop_bars = 48  # 48 horas

    position: Optional[Position] = None
    trades: list[ClosedTrade] = []
    equity = [0.0]  # PnL acumulado
    last_signal_bar = -COOLDOWN_BARS - 1
    signals_generated = 0
    signals_blocked = 0
    ml_hits = 0
    ml_misses = 0
    ml_buys = 0

    closes_array = df["close"].values

    # ML features index (para lookup rápido por timestamp normalizado)
    ml_index: dict[str, int] = {}
    if ml_features_df is not None and "open_time" in ml_features_df.columns:
        for idx, row in ml_features_df.iterrows():
            ts = pd.Timestamp(row["open_time"])
            # Normalizar a tz-naive UTC
            if ts.tzinfo is not None:
                ts = ts.tz_localize(None)
            key = ts.strftime("%Y-%m-%d %H:%M:%S")
            ml_index[key] = idx
        if ml_index:
            sample_keys = list(ml_index.keys())[:3]
            sample_df_times = [df.index[60].strftime("%Y-%m-%d %H:%M:%S") if len(df) > 60 else "N/A"]
            logger.info("ML index: %d entries, sample keys=%s, sample df_time=%s",
                        len(ml_index), sample_keys, sample_df_times)

    for i in range(len(df)):
        current_price = float(df["close"].iloc[i])
        current_high = float(df["high"].iloc[i])
        current_low = float(df["low"].iloc[i])
        current_time = df.index[i]

        # ── SL / TP / Trailing / Time Stop ──────────────────────
        if position is not None:
            position.highest_since_entry = max(position.highest_since_entry, current_high)

            exit_reason = None
            exit_price = current_price

            # Stop Loss
            if current_low <= position.sl_price:
                exit_price = position.sl_price
                exit_reason = "sl"

            # Take Profit
            elif current_high >= position.tp_price:
                exit_price = position.tp_price
                exit_reason = "tp"

            # Time Stop (48h)
            elif (i - position.entry_bar) >= time_stop_bars:
                exit_reason = "time_stop"

            # Trailing Stop (Chandelier Exit) — activo cuando progreso > 65% al TP
            elif position.highest_since_entry > position.entry_price:
                entry = position.entry_price
                tp = position.tp_price
                progress = (position.highest_since_entry - entry) / (tp - entry) if tp > entry else 0
                if progress > 0.65:
                    ind = _compute_indicators_at(df, i)
                    atr = ind["atr_14"] if ind and ind.get("atr_14") else None
                    if atr and atr > 0:
                        chandelier_sl = position.highest_since_entry - 2.0 * atr
                    else:
                        chandelier_sl = entry + (progress - 0.30) * (tp - entry)
                    new_sl = max(position.sl_price, chandelier_sl)
                    if new_sl > position.sl_price:
                        position.sl_price = round(new_sl, 2)

            # Señal técnica de salida (RSI overbought)
            if exit_reason is None and mode in ("rules", "hybrid"):
                ind = _compute_indicators_at(df, i)
                if ind and ind.get("rsi_14") and ind["rsi_14"] > sell_rsi_min:
                    if ind.get("macd_histogram") is not None and ind["macd_histogram"] < sell_macd_hist_max:
                        if (i - last_signal_bar) >= COOLDOWN_BARS:
                            exit_reason = "signal"

            # ML exit signal
            if exit_reason is None and mode in ("ml", "hybrid") and ml_model is not None:
                ml_pred = _get_ml_prediction(ml_model, ml_features_df, ml_index, current_time)
                if ml_pred is not None and ml_pred < -0.0003:  # Predicción bajista
                    exit_reason = "ml_exit"

            # Ejecutar cierre
            if exit_reason is not None:
                pnl_pct = _apply_fees(position.entry_price, exit_price)
                pnl_abs = pnl_pct * position.quantity * position.entry_price

                trade = ClosedTrade(
                    symbol=symbol,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    entry_bar=position.entry_bar,
                    exit_bar=i,
                    pnl=round(pnl_abs, 4),
                    pnl_pct=round(pnl_pct * 100, 4),
                    exit_reason=exit_reason,
                )
                trades.append(trade)
                equity.append(equity[-1] + pnl_abs)
                position = None
                last_signal_bar = i
                continue

            # No exit — actualizar equity con unrealized
            unrealized = _apply_fees(position.entry_price, current_price)
            equity.append(equity[-1])  # Solo realizado en equity
            continue

        # ── Señales de entrada (sin posición abierta) ───────────
        if (i - last_signal_bar) < COOLDOWN_BARS:
            equity.append(equity[-1])
            continue

        entry_signal = False

        # MODO: Reglas técnicas
        if mode in ("rules", "hybrid"):
            ind = _compute_indicators_at(df, i)
            if ind is None:
                equity.append(equity[-1])
                continue

            rsi = ind.get("rsi_14")
            macd_hist = ind.get("macd_histogram")
            adx = ind.get("adx_14")
            sma_20 = ind.get("sma_20")
            sma_50 = ind.get("sma_50")
            atr = ind.get("atr_14")
            vol_ratio = ind.get("volume_ratio")
            close = ind["close"]

            if rsi is None or macd_hist is None or adx is None:
                equity.append(equity[-1])
                continue

            # Entropy
            entropy_ratio = _compute_entropy(closes_array[:i + 1],
                                              window=settings.entropy_window,
                                              bins=settings.entropy_bins)

            # Regime
            hurst = _hurst_exponent(closes_array[max(0, i - 100):i + 1])
            bb_bw = ind.get("bb_bandwidth", 0.0)
            atr_ratio = atr / close if atr and close > 0 else 0.0
            vol_recent = float(df["volume"].iloc[max(0, i - 5):i + 1].mean())
            vol_avg = float(df["volume"].iloc[max(0, i - 100):i + 1].mean())
            regime, regime_conf = _detect_regime(
                adx, bb_bw, atr_ratio, hurst, close,
                sma_20 or close, vol_recent, vol_avg,
            )

            # ── Filtros (replica signal_generator.py con los fixes) ──

            signals_generated += 1

            # Regime filter (Fix 2: threshold 60%)
            if regime == "trending_down" and regime_conf > buy_regime_conf_min:
                signals_blocked += 1
                equity.append(equity[-1])
                continue

            # SMA cross gate (Fix 4: obligatorio)
            sma_aligned = sma_20 is not None and sma_50 is not None and sma_20 > sma_50
            if not sma_aligned:
                signals_blocked += 1
                equity.append(equity[-1])
                continue

            # Condiciones de entrada
            vol_ok = vol_ratio is None or vol_ratio >= 1.2
            if (rsi < buy_rsi_max
                    and macd_hist > buy_macd_hist_min
                    and adx > buy_adx_min
                    and entropy_ratio < buy_entropy_max
                    and vol_ok):
                entry_signal = True

        # MODO: ML
        if mode in ("ml", "hybrid") and not entry_signal and ml_model is not None:
            ml_pred = _get_ml_prediction(ml_model, ml_features_df, ml_index, current_time)
            if ml_pred is not None:
                ml_hits += 1
                if ml_pred > 0.0003:
                    ml_buys += 1
                    if mode == "ml":
                        entry_signal = True
                    elif mode == "hybrid":
                        ind = _compute_indicators_at(df, i)
                        if ind and ind.get("rsi_14") and ind["rsi_14"] < 55:
                            entry_signal = True
            else:
                ml_misses += 1

        # Ejecutar entrada
        if entry_signal:
            ind = ind if 'ind' in dir() else _compute_indicators_at(df, i)
            atr = ind.get("atr_14", 0) if ind else 0
            sl, tp = _compute_sl_tp(current_price, atr or 0)
            notional = 60.0  # ~$60 por trade (igual que el bot real)
            qty = notional / current_price

            position = Position(
                symbol=symbol,
                entry_price=current_price,
                entry_bar=i,
                quantity=qty,
                sl_price=sl,
                tp_price=tp,
            )
            last_signal_bar = i

        equity.append(equity[-1])

    # ── Cerrar posición abierta al final ────────────────────────
    if position is not None:
        exit_price = float(df["close"].iloc[-1])
        pnl_pct = _apply_fees(position.entry_price, exit_price)
        pnl_abs = pnl_pct * position.quantity * position.entry_price
        trades.append(ClosedTrade(
            symbol=symbol, entry_price=position.entry_price,
            exit_price=exit_price, entry_bar=position.entry_bar,
            exit_bar=len(df) - 1, pnl=round(pnl_abs, 4),
            pnl_pct=round(pnl_pct * 100, 4), exit_reason="end_of_data",
        ))
        equity[-1] += pnl_abs

    # ── Calcular métricas ───────────────────────────────────────
    result = _compute_metrics(symbol, mode, len(df), trades, equity)
    result.signals_generated = signals_generated
    result.signals_blocked = signals_blocked
    if mode in ("ml", "hybrid"):
        logger.info("ML stats [%s]: hits=%d, misses=%d, buys=%d",
                    mode, ml_hits, ml_misses, ml_buys)
    return result


def _get_ml_prediction(
    model, features_df: pd.DataFrame | None,
    index: dict, current_time,
) -> Optional[float]:
    """Obtener predicción ML para un timestamp dado."""
    if model is None or features_df is None:
        return None
    ts = pd.Timestamp(current_time)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    key = ts.strftime("%Y-%m-%d %H:%M:%S")
    if key not in index:
        return None
    try:
        feature_cols = getattr(model, "_replay_feature_cols", _ML_FEATURE_COLS)
        if not feature_cols:
            return None
        row = features_df.iloc[index[key]]
        feat_values = [row.get(c, np.nan) for c in feature_cols]
        if any(pd.isna(v) for v in feat_values):
            return None
        pred = model.predict([feat_values])
        result = float(pred[0]) if hasattr(pred[0], '__float__') else float(pred[0])
        return result
    except Exception:
        return None


def _compute_metrics(
    symbol: str, mode: str, total_bars: int,
    trades: list[ClosedTrade], equity: list[float],
) -> ReplayResult:
    """Calcular todas las métricas de performance."""
    result = ReplayResult(symbol=symbol, mode=mode, total_bars=total_bars)
    result.trades = trades
    result.total_trades = len(trades)

    if not trades:
        result.equity_curve = _sample_equity(equity)
        return result

    pnls = [t.pnl for t in trades]
    pnl_pcts = [t.pnl_pct / 100 for t in trades]
    holds = [t.hold_bars for t in trades]

    result.wins = sum(1 for p in pnls if p > 0)
    result.losses = sum(1 for p in pnls if p <= 0)
    result.total_pnl = round(sum(pnls), 2)
    result.win_rate = round(result.wins / len(trades) * 100, 1) if trades else 0
    result.avg_pnl_pct = round(np.mean(pnl_pcts) * 100, 4)
    result.avg_hold_bars = round(np.mean(holds), 1)

    # Sharpe (anualizado para 1h bars)
    if len(pnl_pcts) > 1 and np.std(pnl_pcts) > 0:
        result.sharpe_ratio = round(
            float(np.mean(pnl_pcts) / np.std(pnl_pcts) * np.sqrt(8760 / max(np.mean(holds), 1))), 4
        )

    # Sortino
    downside = [p for p in pnl_pcts if p < 0]
    if downside and np.std(downside) > 0:
        result.sortino_ratio = round(
            float(np.mean(pnl_pcts) / np.std(downside) * np.sqrt(8760 / max(np.mean(holds), 1))), 4
        )

    # Profit Factor
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    result.profit_factor = round(gross_profit / gross_loss, 4) if gross_loss > 0 else 99.0

    # Expectancy (promedio PnL ponderado)
    result.expectancy = round(np.mean(pnls), 4)

    # Max Drawdown
    peak = 0.0
    max_dd = 0.0
    for val in equity:
        if val > peak:
            peak = val
        dd = peak - val
        if dd > max_dd:
            max_dd = dd
    # Como porcentaje del capital base ($60 notional * max_positions)
    base_capital = 60.0 * settings.risk_max_open_positions
    result.max_drawdown_pct = round(max_dd / base_capital * 100, 2) if base_capital > 0 else 0

    result.equity_curve = _sample_equity(equity)
    return result


def _sample_equity(equity: list[float], max_points: int = 500) -> list[dict]:
    """Samplear equity curve a max_points."""
    if len(equity) <= max_points:
        return [{"bar": i, "equity": round(v, 2)} for i, v in enumerate(equity)]
    step = max(1, len(equity) // max_points)
    return [{"bar": i, "equity": round(equity[i], 2)} for i in range(0, len(equity), step)]


# ── Comparación multi-modo ──────────────────────────────────────────
async def run_comparison(
    symbol: str = "BTCUSDT",
    days: int = 90,
    train_ml: bool = True,
) -> dict:
    """Ejecutar replay en los 3 modos y comparar.

    Returns:
        {
            "rules": ReplayResult,
            "ml": ReplayResult | None,
            "hybrid": ReplayResult | None,
            "comparison_table": str,
        }
    """
    logger.info("═" * 60)
    logger.info("STRATEGY REPLAY — %s — %d días", symbol, days)
    logger.info("═" * 60)

    # 1. Rules only
    logger.info("��� Modo RULES (técnico puro)...")
    rules_result = await run_replay(symbol, mode="rules", days=days)

    ml_result = None
    hybrid_result = None
    ml_model = None
    ml_features = None

    # 2. ML training + replay
    if train_ml:
        try:
            logger.info("▶ Entrenando modelo ML...")
            ml_model, ml_features = await _train_ml_for_replay(symbol, days)

            if ml_model is not None:
                logger.info("▶ Modo ML (solo predicciones)...")
                ml_result = await run_replay(
                    symbol, mode="ml", days=days,
                    ml_model=ml_model, ml_features_df=ml_features,
                )

                logger.info("▶ Modo HYBRID (reglas + ML)...")
                hybrid_result = await run_replay(
                    symbol, mode="hybrid", days=days,
                    ml_model=ml_model, ml_features_df=ml_features,
                )
        except Exception as e:
            logger.error("ML training/replay failed: %s", e)

    # 3. Tabla comparativa
    table = _format_comparison(rules_result, ml_result, hybrid_result)

    return {
        "rules": rules_result,
        "ml": ml_result,
        "hybrid": hybrid_result,
        "comparison_table": table,
    }


async def _train_ml_for_replay(symbol: str, days: int):
    """Entrenar modelo LightGBM para el replay usando features directos de klines."""
    try:
        # Cargar klines directamente (mismo método que el replay)
        df = await _load_klines(symbol, "1h", days)
        if df is None or len(df) < 200:
            logger.warning("Not enough klines for ML: %d", len(df) if df is not None else 0)
            return None, None

        # Computar features directamente del DataFrame
        features = _compute_ml_features(df)
        if features is None or len(features) < 200:
            logger.warning("Not enough features after computation: %d",
                           len(features) if features is not None else 0)
            return None, None

        feature_cols = [c for c in features.columns
                        if c not in ("open_time", "close", "logret_next")]

        # Split temporal: 80% train, 20% test
        split_idx = int(len(features) * 0.8)
        train_df = features.iloc[:split_idx]

        X_train = train_df[feature_cols].values
        y_train = train_df["logret_next"].values

        logger.info("ML dataset: %d total, %d train, %d features",
                    len(features), len(X_train), len(feature_cols))

        # Entrenar LightGBM
        try:
            import lightgbm as lgb
            dtrain = lgb.Dataset(X_train, label=y_train)
            params = {
                "objective": "regression",
                "metric": "mae",
                "learning_rate": 0.05,
                "max_depth": 4,
                "min_child_samples": 10,
                "reg_alpha": 0.01,
                "reg_lambda": 0.1,
                "subsample": 0.8,
                "colsample_bytree": 0.7,
                "verbose": -1,
            }
            model = lgb.train(params, dtrain, num_boost_round=200)
            logger.info("LightGBM trained: %d samples, %d features, train period %s → %s",
                        len(X_train), len(feature_cols),
                        train_df["open_time"].iloc[0],
                        train_df["open_time"].iloc[-1])
        except ImportError:
            from sklearn.ensemble import RandomForestRegressor
            model = RandomForestRegressor(
                n_estimators=200, max_depth=8, min_samples_leaf=20,
                random_state=42, n_jobs=-1,
            )
            model.fit(X_train, y_train)
            logger.info("RandomForest fallback trained: %d samples", len(X_train))

        # Guardar feature_cols en el modelo para predicción
        model._replay_feature_cols = feature_cols
        return model, features

    except Exception as e:
        logger.error("ML training error: %s", e, exc_info=True)
        return None, None


# Features columns constante para ML predictions
_ML_FEATURE_COLS: list[str] = []


def _compute_ml_features(df: pd.DataFrame) -> pd.DataFrame:
    """Computar 25 features ML directamente de un DataFrame de klines.

    Sin dependencias externas — usa pandas-ta sobre el DataFrame completo.
    Zero look-ahead: cada feature usa solo datos pasados.
    """
    global _ML_FEATURE_COLS

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    feat = pd.DataFrame(index=df.index)
    feat["open_time"] = df.index
    feat["close"] = close.values

    # Returns
    feat["ret_1h"] = close.pct_change(1)
    feat["ret_3h"] = close.pct_change(3)
    feat["ret_6h"] = close.pct_change(6)
    feat["ret_12h"] = close.pct_change(12)
    feat["ret_24h"] = close.pct_change(24)
    feat["logret_1h"] = np.log(close / close.shift(1))

    # Momentum
    feat["rsi_14"] = ta.rsi(close, length=14)
    feat["rsi_2"] = ta.rsi(close, length=2)
    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    if macd_df is not None:
        hist_col = [c for c in macd_df.columns if "h" in c.lower() or "hist" in c.lower()]
        feat["macd_hist"] = macd_df[hist_col[0]].values if hist_col else 0
    adx_df = ta.adx(high, low, close, length=14)
    if adx_df is not None:
        adx_col = [c for c in adx_df.columns if c.startswith("ADX")]
        feat["adx_14"] = adx_df[adx_col[0]].values if adx_col else 0
        di_plus = [c for c in adx_df.columns if "DMP" in c]
        di_minus = [c for c in adx_df.columns if "DMN" in c]
        if di_plus and di_minus:
            feat["plus_di_minus_di"] = adx_df[di_plus[0]].values - adx_df[di_minus[0]].values

    # Trend
    sma_20 = ta.sma(close, length=20)
    sma_50 = ta.sma(close, length=50)
    ema_12 = ta.ema(close, length=12)
    ema_26 = ta.ema(close, length=26)
    if sma_20 is not None and sma_50 is not None:
        feat["sma20_sma50_ratio"] = sma_20 / sma_50
    if ema_12 is not None and ema_26 is not None:
        feat["ema12_ema26_ratio"] = ema_12 / ema_26

    # Volatility
    atr_14 = ta.atr(high, low, close, length=14)
    if atr_14 is not None:
        feat["atr_pct"] = atr_14 / close
    bb = ta.bbands(close, length=20, std=2)
    if bb is not None:
        bbu = [c for c in bb.columns if "BBU" in c]
        bbl = [c for c in bb.columns if "BBL" in c]
        bbm = [c for c in bb.columns if "BBM" in c]
        if bbu and bbl and bbm:
            feat["bb_width"] = (bb[bbu[0]] - bb[bbl[0]]) / bb[bbm[0]]
            feat["bb_pct_b"] = (close.values - bb[bbl[0]].values) / (bb[bbu[0]].values - bb[bbl[0]].values + 1e-10)
    feat["realized_vol_6"] = feat["logret_1h"].rolling(6).std()
    feat["realized_vol_24"] = feat["logret_1h"].rolling(24).std()

    # Volume
    vol_ma_24 = volume.rolling(24).mean()
    vol_std_24 = volume.rolling(24).std()
    feat["volume_zscore"] = (volume - vol_ma_24) / (vol_std_24 + 1e-10)

    # Calendar
    hours = pd.Series(df.index).dt.hour.values
    feat["hour_sin"] = np.sin(2 * np.pi * hours / 24)
    feat["hour_cos"] = np.cos(2 * np.pi * hours / 24)

    # Target: log-return of next bar
    feat["logret_next"] = np.log(close.shift(-1) / close).values

    # Limpiar NaN
    feature_cols = [c for c in feat.columns if c not in ("open_time", "close", "logret_next")]
    feat.dropna(subset=feature_cols + ["logret_next"], inplace=True)
    feat.reset_index(drop=True, inplace=True)

    _ML_FEATURE_COLS = feature_cols
    logger.info("ML features computed: %d rows, %d features", len(feat), len(feature_cols))
    return feat


def _format_comparison(
    rules: ReplayResult,
    ml: Optional[ReplayResult],
    hybrid: Optional[ReplayResult],
) -> str:
    """Formatear tabla comparativa en texto."""
    rows = [rules]
    if ml:
        rows.append(ml)
    if hybrid:
        rows.append(hybrid)

    header = (
        f"{'Modo':<10} {'Trades':>7} {'Win%':>6} {'PnL':>10} "
        f"{'Sharpe':>8} {'PF':>6} {'MaxDD%':>7} {'Avg Hold':>9} "
        f"{'Blocked':>8}"
    )
    sep = "─" * len(header)

    lines = [sep, header, sep]
    for r in rows:
        line = (
            f"{r.mode:<10} {r.total_trades:>7} {r.win_rate:>5.1f}% "
            f"{'$' + f'{r.total_pnl:+.2f}':>10} {r.sharpe_ratio:>8.2f} "
            f"{r.profit_factor:>6.2f} {r.max_drawdown_pct:>6.1f}% "
            f"{r.avg_hold_bars:>8.1f}h {r.signals_blocked:>8}"
        )
        lines.append(line)

    lines.append(sep)

    # Top trades
    if rules.trades:
        best = max(rules.trades, key=lambda t: t.pnl)
        worst = min(rules.trades, key=lambda t: t.pnl)
        lines.append(f"\nMejor trade (rules): ${best.pnl:+.2f} ({best.pnl_pct:+.1f}%) — {best.exit_reason}")
        lines.append(f"Peor trade (rules):  ${worst.pnl:+.2f} ({worst.pnl_pct:+.1f}%) — {worst.exit_reason}")

    # Exit reasons breakdown
    if rules.trades:
        reasons = {}
        for t in rules.trades:
            reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
        lines.append(f"\nRazones de salida (rules): {reasons}")

    return "\n".join(lines)


# ── API Router ──────────────────────────────────────────────────────
async def run_full_comparison(days: int = 90) -> dict:
    """Correr comparación para todos los símbolos configurados."""
    symbols = [s.strip() for s in settings.quant_symbols.split(",")]
    all_results = {}

    for sym in symbols:
        try:
            result = await run_comparison(sym, days=days, train_ml=True)
            all_results[sym] = result
            print(f"\n{'═' * 60}")
            print(f"  {sym}")
            print(result["comparison_table"])
        except Exception as e:
            logger.error("Replay failed for %s: %s", sym, e)
            all_results[sym] = {"error": str(e)}

    return all_results
