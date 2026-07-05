# -*- coding: utf-8 -*-
"""Backtest lab — replica offline de la estrategia 01-trend-momentum del bot.

Standalone: NO importa código del backend (corre sin Supabase ni pandas_ta).
Replica la lógica de:
  - signal_generator.py (entry/exit gates, perfiles por régimen, cooldowns)
  - regime_detector.py  (árbol de decisión ADX/Hurst/BB/ATR)
  - entropy_filter.py   (Shannon entropy de log-returns, 100 velas, 10 bins)
  - executor.py         (SL/TP por ATR con clamps)
  - trading_loop.py     (trailing chandelier, progress >30% hacia TP)

Datos: klines 1h reales de api.binance.com (público, sin API key).
Anti-overfitting: cada variante se evalúa en mitad A y mitad B del período;
solo se reportan como candidatas las que mejoran PF en AMBAS mitades.

Uso:  python scripts/backtest-lab/lab.py [--months 12] [--symbols BTCUSDT,ETHUSDT]
"""

import argparse
import json
import math
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BINANCE = "https://api.binance.com/api/v3/klines"
OUT_DIR = Path(__file__).parent / "results"

FEE = 0.001        # 0.1% por lado (Binance spot)
SLIPPAGE = 0.0005  # 0.05% por lado

NOTIONAL = {"BTCUSDT": 60.0, "ETHUSDT": 80.0}
SL_ATR = {"BTCUSDT": 1.0, "default": 1.2}
TP_ATR = {"BTCUSDT": 1.5, "default": 2.0}
SL_MAX_PCT, TP_MAX_PCT = 0.03, 0.07
SL_MIN_PCT, TP_MIN_PCT = 0.005, 0.01

# Defaults actuales del bot (config.py + _get_thresholds)
BASE_PARAMS = {
    "buy_rsi_max": 50.0,
    "buy_adx_min": 20.0,
    "buy_entropy_max": 0.75,
    "sell_rsi_min": 65.0,
    "buy_macd_hist_min": -200.0,
    "sell_macd_hist_max": 50.0,
    "buy_regime_confidence_min": 85.0,
    "regime_exit_confidence_min": 80.0,
    "min_hold_bars": 3,            # 180 min en 1h
    "cooldown_bars": 3,            # 180 min signal + post-close
    "sl_atr_mult": None,           # None = per-symbol default
    "tp_atr_mult": None,
    "trailing": True,
    "trail_progress": 0.30,        # activa trailing a este % del camino al TP
    "trail_chand_mult": 2.0,       # multiplicador ATR del chandelier
    "mtf_ema_filter": False,       # close > EMA50(4h)
    "block_plain_ranging": False,  # tratar 'ranging' como bloqueado
    "ranging_needs_hints": 1,      # hints requeridos en 'ranging' (actual: 1)
    "entry_mode": "current",       # current | momentum | donchian | meanrev
    "exit_mode": "current",        # current | trail_only | meanrev
    "max_hold_bars": None,         # time stop opcional
    "bull_filter": False,          # master switch: solo operar si close>SMA30d y SMA30d subiendo
    "bull_col": "bull",            # columna del bull filter (bull=SMA720, bull600=SMA600)
    "tp_cap_pct": None,            # para trail_only: cap de TP (None = sin TP, como turtle puro)
}


# ───────────────────────── data ─────────────────────────

def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    rows = []
    cur = start_ms
    while cur < end_ms:
        r = requests.get(BINANCE, params={
            "symbol": symbol, "interval": interval,
            "startTime": cur, "endTime": end_ms, "limit": 1000,
        }, timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        cur = batch[-1][6] + 1  # close_time + 1
        if len(batch) < 1000:
            break
        time.sleep(0.15)
    df = pd.DataFrame(rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "qv", "n", "tbv", "tbqv", "ig"])
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.drop_duplicates(subset="open_time").reset_index(drop=True)
    return df[["ts", "open", "high", "low", "close", "volume"]]


# ───────────────────────── indicadores (replicas de pandas_ta) ─────────────────────────

def rma(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean()


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    o = df.copy()
    c, h, l = o["close"], o["high"], o["low"]

    o["sma_20"] = c.rolling(20).mean()
    o["sma_50"] = c.rolling(50).mean()
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    o["macd_hist"] = macd - macd.ewm(span=9, adjust=False).mean()
    o["ppo"] = (ema12 - ema26) / ema26 * 100

    # RSI Wilder
    delta = c.diff()
    up = delta.clip(lower=0)
    dn = -delta.clip(upper=0)
    rs = rma(up, 14) / rma(dn, 14)
    o["rsi"] = 100 - 100 / (1 + rs)

    # ATR Wilder
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    o["atr"] = rma(tr, 14)

    # ADX Wilder
    up_m = h.diff()
    dn_m = -l.diff()
    plus_dm = pd.Series(np.where((up_m > dn_m) & (up_m > 0), up_m, 0.0), index=o.index)
    minus_dm = pd.Series(np.where((dn_m > up_m) & (dn_m > 0), dn_m, 0.0), index=o.index)
    atr_s = rma(tr, 14)
    pdi = 100 * rma(plus_dm, 14) / atr_s
    mdi = 100 * rma(minus_dm, 14) / atr_s
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
    o["adx"] = rma(dx, 14)

    # Bollinger bandwidth (20, 2) fraccional
    mid = c.rolling(20).mean()
    sd = c.rolling(20).std(ddof=0)
    o["bb_bw"] = (4 * sd) / mid

    # Volume ratio vs SMA20
    o["vol_ratio"] = o["volume"] / o["volume"].rolling(20).mean()

    # Bollinger lower + canales Donchian (shift(1): solo info de velas previas)
    o["bb_lower"] = mid - 2 * sd
    o["don_hi_40"] = h.rolling(40).max().shift(1)
    o["don_hi_55"] = h.rolling(55).max().shift(1)
    o["don_hi_70"] = h.rolling(70).max().shift(1)
    o["don_lo_20"] = l.rolling(20).min().shift(1)

    # Master switch macro: SMA 30 días (720 velas 1h) con pendiente positiva
    sma_30d = c.rolling(720).mean()
    o["bull"] = (c > sma_30d) & (sma_30d > sma_30d.shift(24))

    # Autocorr lag-1 de returns, ventana rodante 250 (igual que df de 250 velas del bot)
    rets = c.pct_change()
    o["autocorr1"] = rets.rolling(250).apply(
        lambda x: pd.Series(x).autocorr(lag=1), raw=False)

    # EMA50 4h para filtro MTF (solo velas 4h CERRADAS → shift para evitar lookahead)
    c4 = c.copy()
    c4.index = o["ts"]
    closes_4h = c4.resample("4h").last().dropna()
    ema50_4h = closes_4h.ewm(span=50, adjust=False).mean().shift(1)  # solo info de velas 4h previas
    o["ema50_4h"] = ema50_4h.reindex(c4.index, method="ffill").values

    return o


def entropy_ratio_series(closes: np.ndarray, window: int = 100, bins: int = 10) -> np.ndarray:
    """Shannon entropy ratio rodante (réplica de entropy_filter.py)."""
    n = len(closes)
    out = np.full(n, np.nan)
    logc = np.log(closes)
    h_max = math.log2(bins)
    for i in range(window, n):
        lr = np.diff(logc[i - window:i + 1])
        counts, _ = np.histogram(lr, bins=bins)
        total = counts.sum()
        if total == 0:
            continue
        p = counts / total
        p = p[p > 0]
        out[i] = float(-(p * np.log2(p)).sum() / h_max)
    return out


def hurst_rs(prices: np.ndarray, max_lag: int = 20) -> float:
    """Réplica exacta de regime_detector._hurst_exponent."""
    if len(prices) < max_lag * 2:
        return 0.5
    rs_values = []
    for lag in range(2, max_lag + 1):
        n_sub = len(prices) // lag
        rs_for_lag = []
        for i in range(n_sub):
            sub = prices[i * lag:(i + 1) * lag]
            if len(sub) < 3:
                continue
            rets = np.diff(sub)
            dev = np.cumsum(rets - rets.mean())
            r = dev.max() - dev.min()
            s = rets.std(ddof=1)
            rs_for_lag.append(r / (s if s > 0 else 1e-10))
        if rs_for_lag:
            m = float(np.mean(rs_for_lag))
            if m > 0:
                rs_values.append((math.log(lag), math.log(m)))
    if len(rs_values) < 3:
        return 0.5
    x, y = zip(*rs_values)
    try:
        h = float(np.polyfit(x, y, 1)[0])
        return max(0.0, min(1.0, h))
    except Exception:
        return 0.5


def hurst_series(closes: np.ndarray, window: int = 100) -> np.ndarray:
    out = np.full(len(closes), np.nan)
    for i in range(window, len(closes)):
        out[i] = hurst_rs(closes[i - window:i])
    return out


# ───────────────────────── régimen (réplica del decision tree) ─────────────────────────

def classify_regime(adx, hurst, close, sma20, bb_bw, atr_ratio, vol5, volm):
    if any(pd.isna(v) for v in (adx, hurst, close, bb_bw, atr_ratio)):
        return "ranging", 50.0
    if adx > 40 and hurst > 0.6:
        if close > (sma20 if not pd.isna(sma20) else close):
            return "trending_up", min(90.0, 50 + adx)
        return "trending_down", min(90.0, 50 + adx)
    if adx > 25 and hurst > 0.55:
        if close > (sma20 if not pd.isna(sma20) else close):
            return "trending_up", min(75.0, 40 + adx)
        return "trending_down", min(75.0, 40 + adx)
    if bb_bw > 0.08 or atr_ratio > 0.04:
        return "volatile", min(85.0, 50 + bb_bw * 200)
    if adx < 22.0 and 0.4 < hurst < 0.6:
        if atr_ratio <= 0.012 and bb_bw <= 0.06:
            conf = min(85.0, 62 + (22.0 - adx) + max(0.0, (0.012 - atr_ratio) * 1000))
            return "ranging_low_vol", conf
        if atr_ratio >= 0.015 or bb_bw >= 0.07:
            conf = min(85.0, 60 + (22.0 - adx) + min(10.0, atr_ratio * 250))
            return "ranging_high_vol", conf
        return "ranging", min(80.0, 60 + (22.0 - adx))
    if not pd.isna(vol5) and not pd.isna(volm) and vol5 < volm * 0.3:
        return "low_liquidity", 60.0
    return "ranging", 50.0


# ───────────────────────── motor de simulación ─────────────────────────

def clamp_sl_tp(price, sl, tp):
    sl = max(sl, price * (1 - SL_MAX_PCT))
    sl = min(sl, price * (1 - SL_MIN_PCT))
    tp = min(tp, price * (1 + TP_MAX_PCT))
    tp = max(tp, price * (1 + TP_MIN_PCT))
    return sl, tp


def breakeven_threshold(atr_pct):
    if atr_pct is None or atr_pct <= 0 or pd.isna(atr_pct):
        return 0.003
    return max(0.003, min(atr_pct * 0.3, 0.008))


def entry_profile(regime, p):
    prof = {"rsi_max": p["buy_rsi_max"], "adx_min": p["buy_adx_min"], "hints": 0, "blocked": None}
    if regime == "ranging":
        if p["block_plain_ranging"]:
            prof["blocked"] = "ranging blocked"
        else:
            prof.update({"rsi_max": min(prof["rsi_max"], 47.0),
                         "adx_min": max(prof["adx_min"], 21.0),
                         "hints": p["ranging_needs_hints"]})
    elif regime == "ranging_low_vol":
        prof.update({"rsi_max": min(prof["rsi_max"], 45.0),
                     "adx_min": max(prof["adx_min"], 22.0), "hints": 2})
    elif regime in ("ranging_high_vol", "volatile", "low_liquidity"):
        prof["blocked"] = regime
    return prof


def breakout_hints(ppo, ac1, vr):
    n = 0
    if ppo is not None and not pd.isna(ppo) and ppo > 0.0:
        n += 1
    if ac1 is not None and not pd.isna(ac1) and ac1 > 0.02:
        n += 1
    if vr is not None and not pd.isna(vr) and vr > 1.05:
        n += 1
    return n


def simulate(df: pd.DataFrame, symbol: str, params: dict) -> list[dict]:
    """Simula la estrategia sobre velas 1h. Señal en cierre de vela i → entrada en open de i+1."""
    p = params
    sl_mult = p["sl_atr_mult"] or SL_ATR.get(symbol, SL_ATR["default"])
    tp_mult = p["tp_atr_mult"] or TP_ATR.get(symbol, TP_ATR["default"])
    notional = NOTIONAL.get(symbol, 60.0)

    closes = df["close"].values
    trades = []
    pos = None
    last_buy_bar = -10_000
    last_close_bar = -10_000
    consec_losses = 0
    pause_until_bar = -1

    vol_mean_full = df["volume"].expanding().mean().values
    vol_mean_5 = df["volume"].rolling(5).mean().values

    for i in range(260, len(df) - 1):
        row = df.iloc[i]
        nxt = df.iloc[i + 1]

        regime, conf = classify_regime(
            row["adx"], row["hurst"], row["close"], row["sma_20"], row["bb_bw"],
            (row["atr"] / row["close"]) if row["close"] else np.nan,
            vol_mean_5[i], vol_mean_full[i])

        # ── manejo de posición abierta ──
        if pos is not None:
            # 1. SL/TP intrabar en la vela i+1 (peor caso: SL primero)
            exit_price, exit_reason = None, None
            if nxt["low"] <= pos["sl"]:
                exit_price, exit_reason = pos["sl"], "sl"
            elif nxt["high"] >= pos["tp"]:
                exit_price, exit_reason = pos["tp"], "tp"

            # 2. señal de exit en cierre de vela i (ejecuta a close)
            if exit_price is None:
                hold_bars = i - pos["bar"]
                if p["exit_mode"] == "current":
                    pnl_pct = (row["close"] - pos["entry"]) / pos["entry"]
                    be = breakeven_threshold(row["atr"] / row["close"] if row["close"] else None)
                    strong_exit = regime == "trending_down" and conf > 90.0
                    if hold_bars >= p["min_hold_bars"] and (pnl_pct >= be or strong_exit):
                        rsi_exit = row["rsi"] > p["sell_rsi_min"] and row["macd_hist"] < p["sell_macd_hist_max"]
                        regime_exit = regime == "trending_down" and conf > p["regime_exit_confidence_min"]
                        hurst_exit = (not pd.isna(row["hurst"])) and row["hurst"] < 0.40 and row["rsi"] > 55
                        if rsi_exit or regime_exit or hurst_exit:
                            exit_price = row["close"]
                            exit_reason = "signal"
                elif p["exit_mode"] == "meanrev":
                    sma_hit = (not pd.isna(row["sma_20"])) and row["close"] >= row["sma_20"]
                    rsi_norm = (not pd.isna(row["rsi"])) and row["rsi"] > 55
                    timeout = p["max_hold_bars"] and hold_bars >= p["max_hold_bars"]
                    if sma_hit or rsi_norm or timeout:
                        exit_price = row["close"]
                        exit_reason = "meanrev_target" if (sma_hit or rsi_norm) else "timeout"
                elif p["exit_mode"] == "trail_only":
                    if p["max_hold_bars"] and hold_bars >= p["max_hold_bars"]:
                        exit_price, exit_reason = row["close"], "timeout"

            if exit_price is not None:
                qty = pos["qty"]
                fill = exit_price * (1 - SLIPPAGE)
                pnl = qty * (fill - pos["entry"]) - notional * FEE - qty * fill * FEE
                trades.append({
                    "symbol": symbol, "entry_ts": str(pos["ts"]), "exit_ts": str(nxt["ts"]),
                    "entry": pos["entry"], "exit": fill, "reason": exit_reason,
                    "pnl": pnl, "hold_bars": i + 1 - pos["bar"], "regime_at_entry": pos["regime"],
                })
                consec_losses = consec_losses + 1 if pnl < 0 else 0
                if consec_losses >= 3:
                    pause_until_bar = i + 24  # pausa 24h
                    consec_losses = 0
                last_close_bar = i + 1
                pos = None
                continue

            # 3. trailing
            if p["exit_mode"] == "trail_only":
                # chandelier ratchet puro: highest close desde entrada - k*ATR
                pos["hh"] = max(pos.get("hh", pos["entry"]), row["close"])
                if not pd.isna(row["atr"]):
                    chand = pos["hh"] - p["trail_chand_mult"] * row["atr"]
                    if chand > pos["sl"]:
                        pos["sl"] = chand
            elif p["trailing"] and p["exit_mode"] == "current":
                cur = row["close"]
                if cur > pos["entry"]:
                    dist = pos["tp0"] - pos["entry"]
                    if dist > 0:
                        progress = (cur - pos["entry"]) / dist
                        if progress >= p["trail_progress"]:
                            chand = cur - p["trail_chand_mult"] * row["atr"] if not pd.isna(row["atr"]) else None
                            trail_pct = max(0, progress - p["trail_progress"])
                            prog_sl = round(pos["entry"] + trail_pct * dist, 2)
                            new_sl = max(chand, prog_sl) if (chand and chand > pos["entry"]) else prog_sl
                            if new_sl > pos["sl"]:
                                pos["sl"] = new_sl
            continue

        # ── entrada ──
        if i < pause_until_bar:
            continue
        if i - last_buy_bar < p["cooldown_bars"] or i - last_close_bar < p["cooldown_bars"]:
            continue

        if p["bull_filter"] and not bool(row[p["bull_col"]]):
            continue

        mode = p["entry_mode"]
        if mode == "current":
            if regime == "trending_down" and conf > p["buy_regime_confidence_min"]:
                continue
            prof = entry_profile(regime, p)
            if prof["blocked"]:
                continue
            sma_ok = (not pd.isna(row["sma_20"])) and (not pd.isna(row["sma_50"])) and row["sma_20"] > row["sma_50"]
            if not sma_ok:
                h = row["hurst"]
                if pd.isna(h) or row["adx"] <= 30 or h < 0.55:
                    continue
            if breakout_hints(row["ppo"], row["autocorr1"], row["vol_ratio"]) < prof["hints"]:
                continue
            if pd.isna(row["rsi"]) or row["rsi"] >= prof["rsi_max"]:
                continue
            if pd.isna(row["macd_hist"]) or row["macd_hist"] <= p["buy_macd_hist_min"]:
                continue
            if pd.isna(row["adx"]) or row["adx"] <= prof["adx_min"]:
                continue
            if pd.isna(row["entropy"]) or row["entropy"] >= p["buy_entropy_max"]:
                continue
            if p["mtf_ema_filter"]:
                if pd.isna(row["ema50_4h"]) or row["close"] <= row["ema50_4h"]:
                    continue
        elif mode == "momentum":
            # comprar FUERZA: tendencia alineada + RSI en zona de momentum
            if regime in ("volatile", "low_liquidity"):
                continue
            if pd.isna(row["sma_20"]) or pd.isna(row["sma_50"]) or not (row["sma_20"] > row["sma_50"]):
                continue
            if row["close"] <= row["sma_20"]:
                continue
            if pd.isna(row["rsi"]) or not (50.0 <= row["rsi"] < 70.0):
                continue
            if pd.isna(row["adx"]) or row["adx"] <= 25.0:
                continue
            if pd.isna(row["macd_hist"]) or row["macd_hist"] <= 0:
                continue
            if pd.isna(row["entropy"]) or row["entropy"] >= p["buy_entropy_max"]:
                continue
            if p["mtf_ema_filter"]:
                if pd.isna(row["ema50_4h"]) or row["close"] <= row["ema50_4h"]:
                    continue
        elif mode == "donchian":
            # breakout: cierre arriba del máximo de N velas previas (turtle)
            don_col = f"don_hi_{p.get('don_len', 55)}"
            if pd.isna(row[don_col]) or row["close"] < row[don_col]:
                continue
            if regime == "low_liquidity":
                continue
            if p["mtf_ema_filter"]:
                if pd.isna(row["ema50_4h"]) or row["close"] <= row["ema50_4h"]:
                    continue
        elif mode == "meanrev":
            # reversión: pánico de corto plazo, RSI<30 + cierre bajo banda inferior
            if regime == "low_liquidity":
                continue
            if pd.isna(row["rsi"]) or row["rsi"] >= 30.0:
                continue
            if pd.isna(row["bb_lower"]) or row["close"] >= row["bb_lower"]:
                continue

        entry = nxt["open"] * (1 + SLIPPAGE)
        atr = row["atr"]
        if pd.isna(atr) or atr <= 0:
            sl, tp = entry * 0.98, entry * 1.04
        else:
            sl = round(entry - sl_mult * atr, 2)
            tp = round(entry + tp_mult * atr, 2)
            if not (0 < sl < entry < tp):
                sl, tp = entry * 0.98, entry * 1.04
        sl, tp = clamp_sl_tp(entry, sl, tp)
        if p["exit_mode"] in ("trail_only", "meanrev"):
            # sin TP fijo (salida por trailing / target dinámico), o cap lejano opcional
            tp = entry * (1 + p["tp_cap_pct"]) if p["tp_cap_pct"] else float("inf")
        pos = {"bar": i + 1, "ts": nxt["ts"], "entry": entry, "qty": notional / entry,
               "sl": sl, "tp": tp, "tp0": tp, "regime": regime}
        last_buy_bar = i

    return trades


# ───────────────────────── métricas ─────────────────────────

def metrics(trades: list[dict]) -> dict:
    if not trades:
        return {"n": 0, "wr": 0, "pf": 0, "expectancy": 0, "pnl": 0, "max_dd": 0, "sharpe": 0}
    pnls = np.array([t["pnl"] for t in trades])
    wins, losses = pnls[pnls > 0], pnls[pnls <= 0]
    gross_w, gross_l = wins.sum(), abs(losses.sum())
    eq = np.cumsum(pnls)
    dd = float((np.maximum.accumulate(eq) - eq).max()) if len(eq) else 0.0
    return {
        "n": len(pnls),
        "wr": round(100 * len(wins) / len(pnls), 1),
        "pf": round(float(gross_w / gross_l), 3) if gross_l > 0 else float("inf"),
        "expectancy": round(float(pnls.mean()), 4),
        "pnl": round(float(pnls.sum()), 2),
        "max_dd": round(dd, 2),
        "sharpe": round(float(pnls.mean() / pnls.std() * math.sqrt(len(pnls))), 2) if pnls.std() > 0 else 0,
    }


# ───────────────────────── variantes ─────────────────────────

DON_BULL = {"entry_mode": "donchian", "exit_mode": "trail_only",
            "sl_atr_mult": 2.0, "trail_chand_mult": 3.0, "bull_filter": True}


def sensitivity_variants() -> dict[str, dict]:
    """Ronda 4: meseta vs pico — perturbar cada parámetro del ganador donchian_bull."""
    v = {"donchian_bull": dict(DON_BULL)}
    v["don40"] = {**DON_BULL, "don_len": 40}
    v["don70"] = {**DON_BULL, "don_len": 70}
    v["chand25"] = {**DON_BULL, "trail_chand_mult": 2.5}
    v["chand35"] = {**DON_BULL, "trail_chand_mult": 3.5}
    v["sl15"] = {**DON_BULL, "sl_atr_mult": 1.5}
    v["sl25"] = {**DON_BULL, "sl_atr_mult": 2.5}
    v["sin_bull"] = {**DON_BULL, "bull_filter": False}
    v["cooldown6"] = {**DON_BULL, "cooldown_bars": 6}
    return v


def prod_variants() -> dict[str, dict]:
    """Ronda 5: validar la config EXACTA de producción vs la del lab.

    Producción difiere del lab en: SMA600 (no 720, por backfill 30d de la DB)
    y TP cap 15% (el executor siempre persiste un TP).
    """
    v = {"donchian_bull": dict(DON_BULL)}
    v["bull600"] = {**DON_BULL, "bull_col": "bull600"}
    v["tpcap15"] = {**DON_BULL, "tp_cap_pct": 0.15}
    v["prod_exacta"] = {**DON_BULL, "bull_col": "bull600", "tp_cap_pct": 0.15}
    return v


def slope_variants() -> dict[str, dict]:
    """Ronda 6 (2026-07-04): ¿la pendiente ESTRICTA del bull filter es demasiado
    frágil en inflexiones? Comparar donchian_bull (SMA720 estrictamente subiendo)
    contra tolerancias que aceptan una SMA plana o cayendo <=t% en 24 velas.

    Aplicar en prod SOLO si una tolerancia mantiene el PF en la meseta (~1.30)
    en AMBAS mitades (no degradar el edge por operar más).
    """
    v = {"donchian_bull": dict(DON_BULL)}                       # referencia: pendiente estricta
    v["slope_t10"] = {**DON_BULL, "bull_col": "bull_t10"}       # tolera caída <=0.1%/24v
    v["slope_t20"] = {**DON_BULL, "bull_col": "bull_t20"}       # tolera caída <=0.2%/24v
    v["slope_t50"] = {**DON_BULL, "bull_col": "bull_t50"}       # tolera caída <=0.5%/24v
    return v


def variants() -> dict[str, dict]:
    v = {"baseline": {}}
    # ── ganadores robustos ronda 1 ──
    v["cur_rr_notrail"] = {"sl_atr_mult": 1.5, "tp_atr_mult": 3.0, "trailing": False}
    v["cur_rr_latetrail"] = {"sl_atr_mult": 1.5, "tp_atr_mult": 3.0,
                             "trail_progress": 0.60, "trail_chand_mult": 3.0}
    # ── arquetipo: comprar fuerza (momentum clásico) ──
    v["momentum_rr"] = {"entry_mode": "momentum", "sl_atr_mult": 1.5, "tp_atr_mult": 3.0,
                        "trailing": False}
    v["momentum_trail"] = {"entry_mode": "momentum", "exit_mode": "trail_only",
                           "sl_atr_mult": 2.0, "trail_chand_mult": 3.0}
    v["momentum_mtf_rr"] = {"entry_mode": "momentum", "mtf_ema_filter": True,
                            "sl_atr_mult": 1.5, "tp_atr_mult": 3.0, "trailing": False}
    # ── arquetipo: breakout turtle (Donchian 55 + chandelier 3 ATR) ──
    v["donchian_turtle"] = {"entry_mode": "donchian", "exit_mode": "trail_only",
                            "sl_atr_mult": 2.0, "trail_chand_mult": 3.0}
    v["donchian_mtf"] = {"entry_mode": "donchian", "exit_mode": "trail_only",
                         "mtf_ema_filter": True, "sl_atr_mult": 2.0, "trail_chand_mult": 3.0}
    # ── arquetipo: mean-reversion (pánico → vuelta a la media) ──
    v["meanrev_48h"] = {"entry_mode": "meanrev", "exit_mode": "meanrev",
                        "sl_atr_mult": 2.5, "max_hold_bars": 48}
    v["meanrev_24h"] = {"entry_mode": "meanrev", "exit_mode": "meanrev",
                        "sl_atr_mult": 2.0, "max_hold_bars": 24}
    # ── master switch macro (cash en bear) sobre los mejores ──
    v["baseline_bull"] = {"bull_filter": True}
    v["momentum_rr_bull"] = {"entry_mode": "momentum", "sl_atr_mult": 1.5, "tp_atr_mult": 3.0,
                             "trailing": False, "bull_filter": True}
    v["momentum_trail_bull"] = {"entry_mode": "momentum", "exit_mode": "trail_only",
                                "sl_atr_mult": 2.0, "trail_chand_mult": 3.0, "bull_filter": True}
    v["donchian_bull"] = {"entry_mode": "donchian", "exit_mode": "trail_only",
                          "sl_atr_mult": 2.0, "trail_chand_mult": 3.0, "bull_filter": True}
    v["meanrev_48h_bull"] = {"entry_mode": "meanrev", "exit_mode": "meanrev",
                             "sl_atr_mult": 2.5, "max_hold_bars": 48, "bull_filter": True}
    return v


# ───────────────────────── main ─────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    ap.add_argument("--sensitivity", action="store_true",
                    help="ronda de sensibilidad alrededor de donchian_bull")
    ap.add_argument("--prod", action="store_true",
                    help="ronda de validación de la config exacta de producción")
    ap.add_argument("--slope", action="store_true",
                    help="ronda de tolerancia de pendiente del bull filter")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30 * args.months)
    symbols = args.symbols.split(",")

    enriched = {}
    for sym in symbols:
        enr_f = OUT_DIR / f"enriched_{sym}_1h_{args.months}m.parquet"
        if enr_f.exists():
            enriched[sym] = pd.read_parquet(enr_f)
            print(f"[{sym}] dataset enriquecido cacheado: {len(enriched[sym])} velas")
            continue
        cache_f = OUT_DIR / f"klines_{sym}_1h_{args.months}m.parquet"
        if cache_f.exists():
            df = pd.read_parquet(cache_f)
            print(f"[{sym}] klines cacheadas: {len(df)} velas")
        else:
            print(f"[{sym}] descargando klines 1h desde {start.date()}...")
            df = fetch_klines(sym, "1h", int(start.timestamp() * 1000), int(end.timestamp() * 1000))
            df.to_parquet(cache_f)
            print(f"[{sym}] {len(df)} velas descargadas")
        print(f"[{sym}] computando indicadores (entropy + hurst rodantes, paciencia)...")
        df = compute_indicators(df)
        df["entropy"] = entropy_ratio_series(df["close"].values)
        df["hurst"] = hurst_series(df["close"].values)
        df.to_parquet(enr_f)
        enriched[sym] = df

    # columna bull600 (config prod) — barata, se computa post-cache si falta
    for sym, df in enriched.items():
        if "bull600" not in df.columns:
            sma600 = df["close"].rolling(600).mean()
            df["bull600"] = (df["close"] > sma600) & (sma600 > sma600.shift(24))

    # columnas bull con tolerancia de pendiente (ronda --slope, 2026-07-04):
    # el prod exige SMA720 ESTRICTAMENTE subiendo (sma_now > sma_prev). En una
    # inflexión (SMA plana muerta) eso rechaza aunque el precio esté +5% sobre la
    # media. Tolerancia t: aceptar si la SMA no cayó más de t% en 24 velas.
    # Se recomputa siempre (barato: solo rolling mean + shift, sin entropy/hurst).
    for sym, df in enriched.items():
        sma720 = df["close"].rolling(720).mean()
        for tag, tol in (("t10", 0.001), ("t20", 0.002), ("t50", 0.005)):
            df[f"bull_{tag}"] = (df["close"] > sma720) & (sma720 >= sma720.shift(24) * (1 - tol))

    results = {}
    if args.slope:
        variant_set = slope_variants()
    elif args.prod:
        variant_set = prod_variants()
    elif args.sensitivity:
        variant_set = sensitivity_variants()
    else:
        variant_set = variants()
    for name, overrides in variant_set.items():
        params = {**BASE_PARAMS, **overrides}
        all_trades = []
        for sym, df in enriched.items():
            all_trades.extend(simulate(df, sym, params))
        all_trades.sort(key=lambda t: t["entry_ts"])
        mid_ts = str(enriched[symbols[0]]["ts"].iloc[len(enriched[symbols[0]]) // 2])
        half_a = [t for t in all_trades if t["entry_ts"] < mid_ts]
        half_b = [t for t in all_trades if t["entry_ts"] >= mid_ts]
        results[name] = {
            "full": metrics(all_trades),
            "half_a": metrics(half_a),
            "half_b": metrics(half_b),
            "by_regime": {},
            "by_symbol": {},
        }
        for reg in sorted({t["regime_at_entry"] for t in all_trades}):
            results[name]["by_regime"][reg] = metrics([t for t in all_trades if t["regime_at_entry"] == reg])
        for sym in symbols:
            results[name]["by_symbol"][sym] = metrics([t for t in all_trades if t["symbol"] == sym])
        if name == "baseline":
            (OUT_DIR / "baseline_trades.json").write_text(json.dumps(all_trades, indent=1, default=str))

    # reporte
    print("\n" + "=" * 110)
    hdr = f"{'variante':<22} {'n':>4} {'WR%':>6} {'PF':>7} {'exp$':>8} {'PnL$':>8} {'DD$':>7} | {'PF(A)':>7} {'PF(B)':>7} {'nA/nB':>9}"
    print(hdr)
    print("-" * 110)
    ref = next(iter(results))
    for name, r in results.items():
        f, a, b = r["full"], r["half_a"], r["half_b"]
        flag = ""
        if name != ref and a["pf"] > results[ref]["half_a"]["pf"] and b["pf"] > results[ref]["half_b"]["pf"]:
            flag = "  << robusta"
        print(f"{name:<22} {f['n']:>4} {f['wr']:>6} {f['pf']:>7} {f['expectancy']:>8} {f['pnl']:>8} {f['max_dd']:>7} | {a['pf']:>7} {b['pf']:>7} {a['n']:>4}/{b['n']:<4}{flag}")

    print(f"\nPor régimen de entrada ({ref}):")
    for reg, m in results[ref]["by_regime"].items():
        print(f"  {reg:<18} n={m['n']:>4} WR={m['wr']:>5}% PF={m['pf']:>6} PnL=${m['pnl']}")
    print(f"\nPor símbolo ({ref}):")
    for sym, m in results[ref]["by_symbol"].items():
        print(f"  {sym:<10} n={m['n']:>4} WR={m['wr']:>5}% PF={m['pf']:>6} PnL=${m['pnl']} DD=${m['max_dd']}")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    out_f = OUT_DIR / f"lab_results_{stamp}.json"
    out_f.write_text(json.dumps(results, indent=1, default=str))
    print(f"\nResultados guardados en {out_f}")


if __name__ == "__main__":
    main()
