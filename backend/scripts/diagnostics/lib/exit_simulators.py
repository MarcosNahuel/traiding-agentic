"""Exit simulators for the partial-exit A/B replay.

Variants:
- V0 baseline:      ATR×SL_K stop, fixed ATR×TP_K target, no trail
- V1 partial+2ATR:  partial 50% @ +1R, then Chandelier(k=2) on runner
- V2 partial+3ATR:  partial 50% @ +1R, then Chandelier(k=3) on runner
- V3 no-partial+3ATR: full position with Chandelier(k=3) trail (no fixed TP)

All sims operate on tick-level surrogates: the high/low of each 1-minute
kline is enough to detect SL/TP/trailing hits within that minute.
For conservative simulation, when both SL and TP are reachable in the
same bar (low <= SL and high >= TP for a long), we assume SL hits first.

P&L is computed in R-multiples and in quote currency net of fees+slippage.
Fees apply on entry and on each exit leg; slippage applied symmetrically
adverse to the trade direction.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

ExitReason = Literal[
    "SL", "TP", "CHANDELIER", "PARTIAL_THEN_CHANDELIER",
    "PARTIAL_THEN_SL", "PARTIAL_THEN_END", "END_OF_DATA",
]


@dataclass
class Entry:
    symbol: str
    side: Literal["long", "short"]
    entry_ts: pd.Timestamp
    entry_price: float
    atr: float


@dataclass
class ExitResult:
    exit_ts: pd.Timestamp
    exit_reason: ExitReason
    pnl_r: float
    pnl_quote: float
    touched_1r: bool


def _apply_costs_long(entry_price: float, exit_price: float, qty: float,
                      fee_bps: float, slip_bps: float) -> float:
    """P&L for a long position, net of fees and slippage."""
    fee_rate = fee_bps / 10_000.0
    slip = slip_bps / 10_000.0
    eff_entry = entry_price * (1 + slip)
    eff_exit = exit_price * (1 - slip)
    pnl_gross = (eff_exit - eff_entry) * qty
    fees = (eff_entry + eff_exit) * qty * fee_rate
    return pnl_gross - fees


def _apply_costs_short(entry_price: float, exit_price: float, qty: float,
                       fee_bps: float, slip_bps: float) -> float:
    fee_rate = fee_bps / 10_000.0
    slip = slip_bps / 10_000.0
    eff_entry = entry_price * (1 - slip)
    eff_exit = exit_price * (1 + slip)
    pnl_gross = (eff_entry - eff_exit) * qty
    fees = (eff_entry + eff_exit) * qty * fee_rate
    return pnl_gross - fees


def _apply_costs(side: str, entry_price: float, exit_price: float,
                 qty: float, fee_bps: float, slip_bps: float) -> float:
    return (_apply_costs_long(entry_price, exit_price, qty, fee_bps, slip_bps)
            if side == "long"
            else _apply_costs_short(entry_price, exit_price, qty, fee_bps, slip_bps))


def _r_value(side: str, atr: float, sl_k: float) -> float:
    """1R in price units = ATR * SL_K (the SL distance)."""
    if atr <= 0:
        raise ValueError("ATR must be > 0")
    return atr * sl_k


def _bar_iter(klines: pd.DataFrame, entry_ts: pd.Timestamp):
    """Yield bars strictly after entry_ts."""
    after = klines[klines["open_time"] > entry_ts]
    for _, row in after.iterrows():
        yield row


def simulate_v0_baseline(entry: Entry, klines_1m: pd.DataFrame,
                          sl_k: float, tp_k: float,
                          fee_bps: float = 10.0, slip_bps: float = 5.0,
                          notional: float = 100.0) -> ExitResult:
    """Fixed SL and TP, no trail. SL takes priority on conflict bars."""
    r = _r_value(entry.side, entry.atr, sl_k)
    qty = notional / entry.entry_price
    if entry.side == "long":
        sl = entry.entry_price - entry.atr * sl_k
        tp = entry.entry_price + entry.atr * tp_k
    else:
        sl = entry.entry_price + entry.atr * sl_k
        tp = entry.entry_price - entry.atr * tp_k

    touched_1r = False
    for bar in _bar_iter(klines_1m, entry.entry_ts):
        hi, lo = bar["high"], bar["low"]
        # 1R progress check
        if entry.side == "long" and hi >= entry.entry_price + r:
            touched_1r = True
        if entry.side == "short" and lo <= entry.entry_price - r:
            touched_1r = True

        if entry.side == "long":
            if lo <= sl:
                pnl_quote = _apply_costs("long", entry.entry_price, sl, qty, fee_bps, slip_bps)
                return ExitResult(bar["close_time"], "SL", -1.0, pnl_quote, touched_1r)
            if hi >= tp:
                pnl_r = (tp - entry.entry_price) / r
                pnl_quote = _apply_costs("long", entry.entry_price, tp, qty, fee_bps, slip_bps)
                return ExitResult(bar["close_time"], "TP", pnl_r, pnl_quote, True)
        else:
            if hi >= sl:
                pnl_quote = _apply_costs("short", entry.entry_price, sl, qty, fee_bps, slip_bps)
                return ExitResult(bar["close_time"], "SL", -1.0, pnl_quote, touched_1r)
            if lo <= tp:
                pnl_r = (entry.entry_price - tp) / r
                pnl_quote = _apply_costs("short", entry.entry_price, tp, qty, fee_bps, slip_bps)
                return ExitResult(bar["close_time"], "TP", pnl_r, pnl_quote, True)

    # Run out of data — close at last close
    last = klines_1m.iloc[-1]
    pnl_r = ((last["close"] - entry.entry_price) / r if entry.side == "long"
             else (entry.entry_price - last["close"]) / r)
    pnl_quote = _apply_costs(entry.side, entry.entry_price, last["close"], qty, fee_bps, slip_bps)
    return ExitResult(last["close_time"], "END_OF_DATA", pnl_r, pnl_quote, touched_1r)


def _simulate_partial_chandelier(entry: Entry, klines_1m: pd.DataFrame,
                                  sl_k: float, chandelier_k: float,
                                  fee_bps: float, slip_bps: float,
                                  notional: float) -> ExitResult:
    """Partial 50% @ +1R, then Chandelier(k) trail on the runner."""
    r = _r_value(entry.side, entry.atr, sl_k)
    qty_total = notional / entry.entry_price
    qty_partial = qty_total / 2.0
    qty_runner = qty_total - qty_partial

    if entry.side == "long":
        sl = entry.entry_price - entry.atr * sl_k
        partial_target = entry.entry_price + r
    else:
        sl = entry.entry_price + entry.atr * sl_k
        partial_target = entry.entry_price - r

    partial_taken = False
    partial_pnl = 0.0
    # Chandelier state: highest_high since partial (long) / lowest_low since partial (short)
    extreme = None  # high (long) or low (short)
    touched_1r = False
    last_bar = None

    for bar in _bar_iter(klines_1m, entry.entry_ts):
        last_bar = bar
        hi, lo = bar["high"], bar["low"]

        if not partial_taken:
            # Could SL hit before partial?
            if entry.side == "long":
                if lo <= sl:
                    pnl_quote = _apply_costs("long", entry.entry_price, sl, qty_total, fee_bps, slip_bps)
                    return ExitResult(bar["close_time"], "SL", -1.0, pnl_quote, touched_1r)
                if hi >= partial_target:
                    touched_1r = True
                    partial_pnl = _apply_costs("long", entry.entry_price, partial_target,
                                                qty_partial, fee_bps, slip_bps)
                    partial_taken = True
                    extreme = hi
                    # within same bar: continue to runner check using same hi/lo
            else:
                if hi >= sl:
                    pnl_quote = _apply_costs("short", entry.entry_price, sl, qty_total, fee_bps, slip_bps)
                    return ExitResult(bar["close_time"], "SL", -1.0, pnl_quote, touched_1r)
                if lo <= partial_target:
                    touched_1r = True
                    partial_pnl = _apply_costs("short", entry.entry_price, partial_target,
                                                qty_partial, fee_bps, slip_bps)
                    partial_taken = True
                    extreme = lo

        if partial_taken:
            # Update extreme and check Chandelier exit on the runner
            if entry.side == "long":
                if hi > extreme:
                    extreme = hi
                trail = extreme - entry.atr * chandelier_k
                # SL never moves down past initial SL
                effective_stop = max(trail, sl)
                if lo <= effective_stop:
                    runner_pnl = _apply_costs("long", entry.entry_price, effective_stop,
                                               qty_runner, fee_bps, slip_bps)
                    pnl_quote = partial_pnl + runner_pnl
                    pnl_r = pnl_quote / (r * qty_total)
                    return ExitResult(bar["close_time"], "PARTIAL_THEN_CHANDELIER",
                                      pnl_r, pnl_quote, True)
            else:
                if lo < extreme:
                    extreme = lo
                trail = extreme + entry.atr * chandelier_k
                effective_stop = min(trail, sl)
                if hi >= effective_stop:
                    runner_pnl = _apply_costs("short", entry.entry_price, effective_stop,
                                               qty_runner, fee_bps, slip_bps)
                    pnl_quote = partial_pnl + runner_pnl
                    pnl_r = pnl_quote / (r * qty_total)
                    return ExitResult(bar["close_time"], "PARTIAL_THEN_CHANDELIER",
                                      pnl_r, pnl_quote, True)

    # Out of data
    if last_bar is None:
        return ExitResult(entry.entry_ts, "END_OF_DATA", 0.0, 0.0, touched_1r)

    if not partial_taken:
        # Treat as still-open at last close
        pnl_quote = _apply_costs(entry.side, entry.entry_price, last_bar["close"],
                                  qty_total, fee_bps, slip_bps)
        pnl_r = pnl_quote / (r * qty_total)
        return ExitResult(last_bar["close_time"], "END_OF_DATA", pnl_r, pnl_quote, touched_1r)

    # Runner closed at last close
    runner_pnl = _apply_costs(entry.side, entry.entry_price, last_bar["close"],
                               qty_runner, fee_bps, slip_bps)
    pnl_quote = partial_pnl + runner_pnl
    pnl_r = pnl_quote / (r * qty_total)
    return ExitResult(last_bar["close_time"], "PARTIAL_THEN_END", pnl_r, pnl_quote, True)


def simulate_v1_partial_2atr(entry: Entry, klines_1m: pd.DataFrame,
                              sl_k: float,
                              fee_bps: float = 10.0, slip_bps: float = 5.0,
                              notional: float = 100.0) -> ExitResult:
    return _simulate_partial_chandelier(entry, klines_1m, sl_k, chandelier_k=2.0,
                                         fee_bps=fee_bps, slip_bps=slip_bps,
                                         notional=notional)


def simulate_v2_partial_3atr(entry: Entry, klines_1m: pd.DataFrame,
                              sl_k: float,
                              fee_bps: float = 10.0, slip_bps: float = 5.0,
                              notional: float = 100.0) -> ExitResult:
    return _simulate_partial_chandelier(entry, klines_1m, sl_k, chandelier_k=3.0,
                                         fee_bps=fee_bps, slip_bps=slip_bps,
                                         notional=notional)


def simulate_v3_no_partial_3atr(entry: Entry, klines_1m: pd.DataFrame,
                                  sl_k: float,
                                  fee_bps: float = 10.0, slip_bps: float = 5.0,
                                  notional: float = 100.0) -> ExitResult:
    """No partial. Chandelier(k=3) trail on the whole position."""
    r = _r_value(entry.side, entry.atr, sl_k)
    qty = notional / entry.entry_price
    if entry.side == "long":
        sl = entry.entry_price - entry.atr * sl_k
    else:
        sl = entry.entry_price + entry.atr * sl_k
    extreme = entry.entry_price
    touched_1r = False
    last_bar = None

    for bar in _bar_iter(klines_1m, entry.entry_ts):
        last_bar = bar
        hi, lo = bar["high"], bar["low"]
        if entry.side == "long" and hi >= entry.entry_price + r:
            touched_1r = True
        if entry.side == "short" and lo <= entry.entry_price - r:
            touched_1r = True

        if entry.side == "long":
            if hi > extreme:
                extreme = hi
            trail = extreme - entry.atr * 3.0
            effective_stop = max(trail, sl)
            if lo <= effective_stop:
                pnl_quote = _apply_costs("long", entry.entry_price, effective_stop,
                                          qty, fee_bps, slip_bps)
                reason: ExitReason = "SL" if effective_stop == sl else "CHANDELIER"
                pnl_r = pnl_quote / (r * qty)
                return ExitResult(bar["close_time"], reason, pnl_r, pnl_quote, touched_1r)
        else:
            if lo < extreme:
                extreme = lo
            trail = extreme + entry.atr * 3.0
            effective_stop = min(trail, sl)
            if hi >= effective_stop:
                pnl_quote = _apply_costs("short", entry.entry_price, effective_stop,
                                          qty, fee_bps, slip_bps)
                reason = "SL" if effective_stop == sl else "CHANDELIER"
                pnl_r = pnl_quote / (r * qty)
                return ExitResult(bar["close_time"], reason, pnl_r, pnl_quote, touched_1r)

    if last_bar is None:
        return ExitResult(entry.entry_ts, "END_OF_DATA", 0.0, 0.0, touched_1r)
    pnl_quote = _apply_costs(entry.side, entry.entry_price, last_bar["close"],
                              qty, fee_bps, slip_bps)
    pnl_r = pnl_quote / (r * qty)
    return ExitResult(last_bar["close_time"], "END_OF_DATA", pnl_r, pnl_quote, touched_1r)
