#!/usr/bin/env python3
"""Backtest-first evidence for Strategy 02 (mean-reversal oversold).

Antes de implementar la estrategia 02 en el hot-path, este script mide si el
patrón "comprar oversold extremo contra-tendencia" tiene edge sobre data REAL,
no sobre la anécdota del único trade de +8.4% del 11-abr (selection bias).

- Datos: klines públicos de Binance (no requiere auth ni el backend roto).
- Lógica: reusa los predicados de reversión del motor de backtest
  (mean_reversion_v2 z-score, rsi_reversal) + la variante "deep oversold" que
  especifica docs/knowledge-base/strategies/02-reversal-oversold.md (RSI<20).
- Simulador: event-driven, SL/TP intrabar (high/low), fees+slippage realistas.
- Ventanas: período completo + sub-ventana bear (últimos 60d) — para ver si el
  edge sobrevive al régimen que sangró en mayo.

Uso:
    python scripts/backtest-reversal.py
    python scripts/backtest-reversal.py --days 240 --symbols ETHUSDT,BTCUSDT
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
import pandas_ta_classic as ta

BINANCE_HOSTS = [
    "https://api.binance.com",
    "https://data-api.binance.vision",
]

# Costos round-trip (mismo supuesto que backtester.py)
FEES = 0.001       # 0.1% por lado
SLIPPAGE = 0.0005  # 0.05% por lado


# ───────────────────────── data ─────────────────────────

def fetch_klines(symbol: str, interval: str, days: int) -> pd.DataFrame:
    """Baja `days` de klines paginando (Binance da máx 1000 por request)."""
    ms_per_bar = {"1h": 3_600_000, "15m": 900_000, "4h": 14_400_000}[interval]
    total = days * (86_400_000 // ms_per_bar)
    end = int(time.time() * 1000)
    rows: list[list] = []
    remaining = total
    while remaining > 0:
        limit = min(1000, remaining)
        start = end - limit * ms_per_bar
        url = (
            f"/api/v3/klines?symbol={symbol}&interval={interval}"
            f"&startTime={start}&endTime={end}&limit={limit}"
        )
        data = _get_json(url)
        if not data:
            break
        rows = data + rows
        end = data[0][0] - 1
        remaining -= len(data)
        if len(data) < limit:
            break
    df = pd.DataFrame(
        rows,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "qv", "trades", "tb", "tq", "ignore",
        ],
    )
    df = df.drop_duplicates(subset="open_time").sort_values("open_time")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    df.index = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df[["open", "high", "low", "close", "volume"]]


def _get_json(path: str):
    last_err = None
    for host in BINANCE_HOSTS:
        try:
            req = urllib.request.Request(host + path, headers={"User-Agent": "traid-backtest/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    print(f"  ! fetch failed for {path}: {last_err}", file=sys.stderr)
    return None


# ──────────────────── signal predicates ────────────────────
# mean_reversion_v2 y rsi_reversal son COPIA VERBATIM de la lógica de
# backend/app/services/backtester.py (para no medir algo distinto a lo que el
# motor ya implementa). deep_oversold_02 es la spec del doc 02 del KB.

def _safe_div(a: pd.Series, b: pd.Series, default: float = 0.0) -> pd.Series:
    out = a / b.replace(0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan).fillna(default)


def sig_mean_reversion_v2(df: pd.DataFrame, p: dict) -> tuple[pd.Series, pd.Series, dict]:
    z_window = int(p.get("z_window", 50))
    z_entry = float(p.get("z_entry", -2.0))
    z_exit = float(p.get("z_exit", 0.0))
    z_stop = float(p.get("z_stop", -3.5))
    adx_max = float(p.get("adx_max", 20.0))
    rsi_entry = float(p.get("rsi_entry", 30.0))
    rsi_exit = float(p.get("rsi_exit", 55.0))
    close = df["close"]
    mean = ta.sma(close, length=z_window)
    std = close.rolling(z_window).std()
    z = _safe_div(close - mean, std)
    adx_df = ta.adx(df["high"], df["low"], close, length=14)
    adx = adx_df.get("ADX_14") if adx_df is not None else pd.Series(np.nan, index=df.index)
    rsi = ta.rsi(close, length=14)
    entries = (z < z_entry) & (adx < adx_max) & (rsi < rsi_entry)
    exits = (z > z_exit) | (rsi > rsi_exit) | (adx > (adx_max + 5)) | (z < z_stop)
    return entries.fillna(False), exits.fillna(False), {"max_hold_bars": int(p.get("max_hold_bars", 24))}


def sig_rsi_reversal(df: pd.DataFrame, p: dict) -> tuple[pd.Series, pd.Series, dict]:
    oversold = float(p.get("oversold", 30))
    overbought = float(p.get("overbought", 70))
    rsi = ta.rsi(df["close"], length=int(p.get("rsi_period", 14)))
    entries = (rsi > oversold) & (rsi.shift(1) <= oversold)
    exits = (rsi < overbought) & (rsi.shift(1) >= overbought)
    return entries.fillna(False), exits.fillna(False), {"max_hold_bars": int(p.get("max_hold_bars", 0))}


def sig_deep_oversold_02(df: pd.DataFrame, p: dict) -> tuple[pd.Series, pd.Series, dict]:
    """Spec de docs/knowledge-base/strategies/02-reversal-oversold.md.

    Entry: RSI<20 (capitulación) + precio < BB lower + ATR% < cap (no crash).
    Exit señal: RSI>rsi_exit. SL: -sl_atr*ATR (tight). Time stop: max_hold_bars.
    """
    rsi_entry = float(p.get("rsi_entry", 20.0))
    rsi_exit = float(p.get("rsi_exit", 45.0))
    atr_pct_cap = float(p.get("atr_pct_cap", 0.05))
    bb_len = int(p.get("bb_length", 20))
    close = df["close"]
    rsi = ta.rsi(close, length=14)
    atr = ta.atr(df["high"], df["low"], close, length=14)
    atr_pct = _safe_div(atr, close)
    bb = ta.bbands(close, length=bb_len, std=2.0)
    lower = bb.get(f"BBL_{bb_len}_2.0") if bb is not None else pd.Series(np.nan, index=df.index)
    entries = (rsi < rsi_entry) & (close < lower) & (atr_pct < atr_pct_cap)
    exits = rsi > rsi_exit
    return entries.fillna(False), exits.fillna(False), {
        "max_hold_bars": int(p.get("max_hold_bars", 6)),
        "sl_atr": float(p.get("sl_atr", 1.5)),
    }


STRATS = {
    "mean_reversion_v2": sig_mean_reversion_v2,
    "rsi_reversal": sig_rsi_reversal,
    "deep_oversold_02": sig_deep_oversold_02,
}


# ──────────────────── event-driven simulator ────────────────────

@dataclass
class Metrics:
    label: str
    trades: int
    win_rate: float
    profit_factor: float
    total_return_pct: float
    max_dd_pct: float
    expectancy_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    sl_hits: int
    signal_exits: int
    time_stops: int


def simulate(df: pd.DataFrame, entries: pd.Series, exits: pd.Series, meta: dict, label: str) -> Metrics:
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    atr = ta.atr(df["high"], df["low"], df["close"], length=14).values
    max_hold = int(meta.get("max_hold_bars", 0))
    sl_atr = float(meta.get("sl_atr", 0.0))
    en = entries.values
    ex = exits.values

    in_pos = False
    entry_px = 0.0
    stop_px = 0.0
    bars_held = 0
    rets: list[float] = []
    sl_hits = sig_ex = time_st = 0
    cost = FEES + SLIPPAGE  # por lado

    for i in range(len(close)):
        if not in_pos:
            if en[i] and not np.isnan(close[i]):
                in_pos = True
                entry_px = close[i] * (1 + cost)
                bars_held = 0
                stop_px = (close[i] - sl_atr * atr[i]) if (sl_atr > 0 and not np.isnan(atr[i])) else 0.0
            continue
        bars_held += 1
        # SL intrabar (prioridad 1)
        if stop_px > 0 and low[i] <= stop_px:
            exit_px = stop_px * (1 - cost)
            rets.append(exit_px / entry_px - 1)
            sl_hits += 1
            in_pos = False
            continue
        # señal de salida (close)
        if ex[i]:
            exit_px = close[i] * (1 - cost)
            rets.append(exit_px / entry_px - 1)
            sig_ex += 1
            in_pos = False
            continue
        # time stop
        if max_hold > 0 and bars_held >= max_hold:
            exit_px = close[i] * (1 - cost)
            rets.append(exit_px / entry_px - 1)
            time_st += 1
            in_pos = False
            continue

    r = np.array(rets) if rets else np.array([])
    n = len(r)
    if n == 0:
        return Metrics(label, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    wins = r[r > 0]
    losses = r[r < 0]
    gross_win = wins.sum()
    gross_loss = -losses.sum()
    pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    equity = np.cumprod(1 + r)
    peak = np.maximum.accumulate(equity)
    max_dd = float(((equity - peak) / peak).min()) if n else 0.0
    return Metrics(
        label=label,
        trades=n,
        win_rate=round(100 * len(wins) / n, 1),
        profit_factor=round(pf, 3) if pf != float("inf") else 999.0,
        total_return_pct=round(100 * (equity[-1] - 1), 2),
        max_dd_pct=round(100 * max_dd, 2),
        expectancy_pct=round(100 * r.mean(), 4),
        avg_win_pct=round(100 * wins.mean(), 3) if len(wins) else 0.0,
        avg_loss_pct=round(100 * losses.mean(), 3) if len(losses) else 0.0,
        sl_hits=sl_hits,
        signal_exits=sig_ex,
        time_stops=time_st,
    )


PARAM_SETS = {
    "mean_reversion_v2": {"z_window": 50, "z_entry": -2.0, "z_exit": 0.0, "adx_max": 20,
                          "rsi_entry": 30, "rsi_exit": 55, "max_hold_bars": 24},
    "rsi_reversal": {"rsi_period": 14, "oversold": 30, "overbought": 70, "max_hold_bars": 24},
    "deep_oversold_02": {"rsi_entry": 20, "rsi_exit": 45, "sl_atr": 1.5, "atr_pct_cap": 0.05,
                         "max_hold_bars": 6},
}


def run(symbols: list[str], days: int, bear_days: int, interval: str = "1h") -> None:
    print(f"\n{'='*78}\nBACKTEST-FIRST — Strategy 02 (reversal) | {interval} | {days}d full / {bear_days}d bear")
    print(f"fees={FEES*100:.2f}%/side slippage={SLIPPAGE*100:.3f}%/side\n{'='*78}")
    header = f"{'window':>6} {'symbol':>8} {'strategy':>20} {'trades':>7} {'WR%':>6} {'PF':>7} {'ret%':>8} {'DD%':>8} {'exp%':>8} {'SL':>4} {'sig':>4} {'time':>5}"
    for sym in symbols:
        print(f"\n--- {sym} ---")
        df = fetch_klines(sym, interval, days)
        if df.empty or len(df) < 60:
            print(f"  ! sin datos suficientes ({len(df)} bars)")
            continue
        bear_bars = bear_days * 24
        df_bear = df.iloc[-bear_bars:] if len(df) > bear_bars else df
        print(f"  {len(df)} bars | {df.index[0].date()} → {df.index[-1].date()} | bear={df_bear.index[0].date()}→")
        print(header)
        for window_name, d in (("full", df), ("bear", df_bear)):
            for sid, fn in STRATS.items():
                try:
                    en, ex, meta = fn(d, PARAM_SETS[sid])
                    m = simulate(d, en, ex, meta, sid)
                except Exception as e:  # noqa: BLE001
                    print(f"  ! {sid} error: {e}")
                    continue
                print(f"{window_name:>6} {sym:>8} {sid:>20} {m.trades:>7} {m.win_rate:>6} "
                      f"{m.profit_factor:>7} {m.total_return_pct:>8} {m.max_dd_pct:>8} "
                      f"{m.expectancy_pct:>8} {m.sl_hits:>4} {m.signal_exits:>4} {m.time_stops:>5}")
    print(f"\n{'='*78}")
    print("GATE: la 02 se activa SOLO si PF>1.2 y expectancy>0 en AMBAS ventanas,")
    print("      con >=20 trades. <20 trades = muestra insuficiente (no concluyente).")
    print(f"{'='*78}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=240)
    ap.add_argument("--bear-days", type=int, default=60)
    ap.add_argument("--symbols", default="ETHUSDT,BTCUSDT")
    ap.add_argument("--interval", default="1h")
    args = ap.parse_args()
    run(args.symbols.split(","), args.days, args.bear_days, args.interval)
