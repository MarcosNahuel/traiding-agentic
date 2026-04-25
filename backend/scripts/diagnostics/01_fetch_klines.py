"""Fetch klines from Binance Live (public REST) and persist to parquet.

Usage:
    python -m backend.scripts.diagnostics.01_fetch_klines \
        --start 2026-01-01 --end 2026-04-25 \
        --symbols ETHUSDT,BTCUSDT --intervals 1m,1h \
        --out data/diagnostics/klines.parquet

Idempotent: if the parquet already covers the requested range, it skips.
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BINANCE_BASE = "https://api.binance.com"
KLINES_PATH = "/api/v3/klines"
LIMIT = 1000  # max per request

INTERVAL_MS = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "1h": 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
}

KLINE_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades",
    "taker_buy_base", "taker_buy_quote", "ignore",
]


@dataclass
class FetchSpec:
    symbol: str
    interval: str
    start_ms: int
    end_ms: int


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", required=True, help="ISO date YYYY-MM-DD (UTC)")
    p.add_argument("--end", required=True, help="ISO date YYYY-MM-DD (UTC, exclusive)")
    p.add_argument("--symbols", default="ETHUSDT,BTCUSDT")
    p.add_argument("--intervals", default="1m,1h")
    p.add_argument("--out", default="data/diagnostics/klines.parquet")
    p.add_argument("--force", action="store_true", help="Refetch even if range covered")
    return p.parse_args()


def to_ms(date_str: str) -> int:
    dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def fetch_chunk(symbol: str, interval: str, start_ms: int, end_ms: int) -> list:
    """Single Binance request. Returns raw list of klines."""
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": LIMIT,
    }
    r = requests.get(BINANCE_BASE + KLINES_PATH, params=params, timeout=15)
    if r.status_code == 429:
        retry_after = int(r.headers.get("Retry-After", "10"))
        print(f"  [rate-limit] sleeping {retry_after}s", file=sys.stderr)
        time.sleep(retry_after)
        return fetch_chunk(symbol, interval, start_ms, end_ms)
    r.raise_for_status()
    used = r.headers.get("X-MBX-USED-WEIGHT-1M", "?")
    if int(used) > 1000 if used.isdigit() else False:
        time.sleep(2)
    return r.json()


def fetch_all(spec: FetchSpec) -> pd.DataFrame:
    """Paginate through the entire range for a single (symbol, interval)."""
    interval_ms = INTERVAL_MS[spec.interval]
    chunks: list = []
    cursor = spec.start_ms
    n_requests = 0

    while cursor < spec.end_ms:
        chunk_end = min(cursor + LIMIT * interval_ms, spec.end_ms)
        raw = fetch_chunk(spec.symbol, spec.interval, cursor, chunk_end)
        n_requests += 1
        if not raw:
            # advance cursor by one chunk to avoid infinite loop on empty responses
            cursor = chunk_end
            continue
        chunks.extend(raw)
        last_open = raw[-1][0]
        cursor = last_open + interval_ms
        # gentle pacing
        time.sleep(0.2)

    if not chunks:
        return pd.DataFrame()

    df = pd.DataFrame(chunks, columns=KLINE_COLS)
    df["symbol"] = spec.symbol
    df["interval"] = spec.interval
    # numeric cols
    for col in ["open", "high", "low", "close", "volume", "quote_volume",
                "taker_buy_base", "taker_buy_quote"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    print(f"  fetched {len(df):>7} rows in {n_requests} requests "
          f"({spec.symbol} {spec.interval})")
    return df[["symbol", "interval", "open_time", "open", "high", "low",
               "close", "volume", "close_time"]]


def existing_coverage(out_path: Path) -> dict[tuple[str, str], tuple[pd.Timestamp, pd.Timestamp]]:
    if not out_path.exists():
        return {}
    df = pd.read_parquet(out_path)
    cov: dict[tuple[str, str], tuple[pd.Timestamp, pd.Timestamp]] = {}
    for (sym, iv), g in df.groupby(["symbol", "interval"]):
        cov[(sym, iv)] = (g["open_time"].min(), g["open_time"].max())
    return cov


def main() -> int:
    args = parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    start_ms = to_ms(args.start)
    end_ms = to_ms(args.end)
    symbols = [s.strip().upper() for s in args.symbols.split(",")]
    intervals = [i.strip() for i in args.intervals.split(",")]

    cov = {} if args.force else existing_coverage(out_path)
    new_frames: list[pd.DataFrame] = []
    skipped: list[str] = []

    for sym in symbols:
        for iv in intervals:
            spec_start = start_ms
            spec_end = end_ms
            if (sym, iv) in cov and not args.force:
                cmin, cmax = cov[(sym, iv)]
                cmin_ms = int(cmin.timestamp() * 1000)
                cmax_ms = int(cmax.timestamp() * 1000)
                if cmin_ms <= start_ms and cmax_ms >= end_ms - INTERVAL_MS[iv]:
                    skipped.append(f"{sym} {iv}")
                    continue
                # fetch only the missing tail (simplification — full re-coverage
                # would also need the missing head, but for the sprint we
                # assume monotonically growing range)
                if cmax_ms >= start_ms:
                    spec_start = cmax_ms + INTERVAL_MS[iv]
            print(f"[fetch] {sym} {iv} {datetime.fromtimestamp(spec_start/1000, tz=timezone.utc)} -> "
                  f"{datetime.fromtimestamp(spec_end/1000, tz=timezone.utc)}")
            df = fetch_all(FetchSpec(sym, iv, spec_start, spec_end))
            if not df.empty:
                new_frames.append(df)

    if skipped:
        print(f"[skip] already covered: {', '.join(skipped)}")

    if not new_frames:
        print("[done] no new data fetched.")
        return 0

    new_df = pd.concat(new_frames, ignore_index=True)
    if out_path.exists() and not args.force:
        old_df = pd.read_parquet(out_path)
        combined = pd.concat([old_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(
            subset=["symbol", "interval", "open_time"], keep="last"
        ).sort_values(["symbol", "interval", "open_time"]).reset_index(drop=True)
    else:
        combined = new_df.sort_values(
            ["symbol", "interval", "open_time"]).reset_index(drop=True)

    combined.to_parquet(out_path, index=False)
    print(f"[done] wrote {len(combined):,} rows to {out_path}")

    # summary
    print("\nCoverage summary:")
    for (sym, iv), g in combined.groupby(["symbol", "interval"]):
        print(f"  {sym} {iv}: {len(g):>7} rows  "
              f"{g['open_time'].min()} → {g['open_time'].max()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
