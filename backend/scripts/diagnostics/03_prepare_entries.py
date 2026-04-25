"""Prepare entries.parquet from trades.csv + klines.

Deviation from original spec §4.2 step 03:
Original plan was to re-derive entries by re-running signal_generator
against historical klines. That's high-risk (match rate hard to predict,
big surface for reproduction bugs).

Instead, we use the **actual entry timestamps from Supabase** as seeds
for the partial-exit A/B test. This answers the operational question
directly: "given the entries the bot actually opened, would V0-V3 have
produced different outcomes?". The drift audit (script 02) separately
addresses pre-fix contamination, so the A/B can split on `pre_fix` vs
`post_fix` to isolate clean signal.

Output: entries.parquet with one row per Supabase trade, with ATR_14
computed from the 1h klines at entry time.

Usage:
    python -m backend.scripts.diagnostics.03_prepare_entries \
        --trades data/diagnostics/trades.csv \
        --klines data/diagnostics/klines.parquet \
        --fix-date 2026-04-18 \
        --out data/diagnostics/entries.parquet
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.scripts.diagnostics.lib.kline_loader import KlineLoader  # noqa: E402

ATR_PERIOD = 14


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trades", default="data/diagnostics/trades.csv")
    p.add_argument("--klines", default="data/diagnostics/klines.parquet")
    p.add_argument("--fix-date", default="2026-04-18")
    p.add_argument("--out", default="data/diagnostics/entries.parquet")
    return p.parse_args()


def compute_atr(klines_1h: pd.DataFrame, ts: pd.Timestamp,
                period: int = ATR_PERIOD) -> float | None:
    """ATR_14 (Wilder) computed from the `period` bars preceding ts."""
    df = klines_1h[klines_1h["open_time"] < ts].tail(period + 1)
    if len(df) < period + 1:
        return None
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    return float(tr.tail(period).mean())


def main() -> int:
    args = parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    trades = pd.read_csv(args.trades)
    trades["opened_at"] = pd.to_datetime(trades["opened_at"], utc=True)
    trades["closed_at"] = pd.to_datetime(trades["closed_at"], utc=True)
    fix_date = pd.Timestamp(args.fix_date, tz="UTC")

    loader = KlineLoader(args.klines)

    rows: list[dict] = []
    skipped = 0
    for _, t in trades.iterrows():
        # Load 1h klines for this symbol
        h = loader.slice(t["symbol"], "1h")
        if h.empty:
            skipped += 1
            continue
        atr = compute_atr(h, t["opened_at"])
        if atr is None or atr <= 0:
            skipped += 1
            continue
        rows.append({
            "trade_id": t["id"],
            "symbol": t["symbol"],
            "side": t["side"],
            "entry_ts": t["opened_at"],
            "entry_price": float(t["entry_price"]),
            "atr": atr,
            "actual_exit_ts": t["closed_at"],
            "actual_exit_price": float(t["exit_price"]),
            "actual_realized_pnl": float(t["realized_pnl"]) if pd.notna(t["realized_pnl"]) else 0.0,
            "actual_pnl_pct": float(t["realized_pnl_percent"]) if pd.notna(t["realized_pnl_percent"]) else 0.0,
            "stop_loss_price": float(t["stop_loss_price"]) if pd.notna(t["stop_loss_price"]) else np.nan,
            "take_profit_price": float(t["take_profit_price"]) if pd.notna(t["take_profit_price"]) else np.nan,
            "post_fix": t["opened_at"] >= fix_date,
        })

    df = pd.DataFrame(rows)
    df.to_parquet(out_path, index=False)
    print(f"[done] {len(df)} entries written to {out_path} ({skipped} skipped)")
    print(f"  by symbol: {df['symbol'].value_counts().to_dict()}")
    print(f"  pre_fix={(~df['post_fix']).sum()}, post_fix={df['post_fix'].sum()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
