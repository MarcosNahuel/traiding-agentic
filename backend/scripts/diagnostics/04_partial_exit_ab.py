"""Run V0-V3 exit simulators on every entry and produce comparative report.

Usage:
    python -m backend.scripts.diagnostics.04_partial_exit_ab \
        --entries data/diagnostics/entries.parquet \
        --klines data/diagnostics/klines.parquet \
        --sl-k 1.5 --tp-k 2.5 \
        --fee-bps 10 --slip-bps 5 \
        --notional 100 \
        --out backend/scripts/diagnostics/reports/02-partial-exit-ab.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import timedelta

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.scripts.diagnostics.lib.kline_loader import KlineLoader  # noqa: E402
from backend.scripts.diagnostics.lib.exit_simulators import (  # noqa: E402
    Entry,
    simulate_v0_baseline,
    simulate_v1_partial_2atr,
    simulate_v2_partial_3atr,
    simulate_v3_no_partial_3atr,
)

VARIANTS = {
    "V0_baseline": "fixed SL/TP",
    "V1_partial_2atr": "partial 50%@1R + chandelier k=2",
    "V2_partial_3atr": "partial 50%@1R + chandelier k=3",
    "V3_no_partial_3atr": "no partial + chandelier k=3",
}

# Cap how far forward we simulate from entry. None = run to data end.
MAX_HORIZON_HOURS = 240  # 10 days


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--entries", default="data/diagnostics/entries.parquet")
    p.add_argument("--klines", default="data/diagnostics/klines.parquet")
    p.add_argument("--sl-k", type=float, default=1.5)
    p.add_argument("--tp-k", type=float, default=2.5)
    p.add_argument("--fee-bps", type=float, default=10.0)
    p.add_argument("--slip-bps", type=float, default=5.0)
    p.add_argument("--notional", type=float, default=100.0)
    p.add_argument("--out", default="backend/scripts/diagnostics/reports/02-partial-exit-ab.md")
    return p.parse_args()


def run_variant(name: str, entries: pd.DataFrame, loader: KlineLoader,
                sl_k: float, tp_k: float, fee_bps: float, slip_bps: float,
                notional: float) -> pd.DataFrame:
    sim = {
        "V0_baseline":         lambda e, k: simulate_v0_baseline(e, k, sl_k, tp_k, fee_bps, slip_bps, notional),
        "V1_partial_2atr":     lambda e, k: simulate_v1_partial_2atr(e, k, sl_k, fee_bps, slip_bps, notional),
        "V2_partial_3atr":     lambda e, k: simulate_v2_partial_3atr(e, k, sl_k, fee_bps, slip_bps, notional),
        "V3_no_partial_3atr":  lambda e, k: simulate_v3_no_partial_3atr(e, k, sl_k, fee_bps, slip_bps, notional),
    }[name]
    rows: list[dict] = []
    for _, row in entries.iterrows():
        entry_ts = row["entry_ts"]
        end_ts = entry_ts + timedelta(hours=MAX_HORIZON_HOURS)
        klines = loader.slice(row["symbol"], "1m", start=entry_ts, end=end_ts)
        if klines.empty:
            continue
        e = Entry(row["symbol"], row["side"], entry_ts,
                  float(row["entry_price"]), float(row["atr"]))
        try:
            result = sim(e, klines)
        except Exception as exc:
            print(f"  [warn] sim {name} failed for {row['trade_id']}: {exc}",
                  flush=True)
            continue
        rows.append({
            "trade_id": row["trade_id"],
            "symbol": row["symbol"],
            "post_fix": bool(row["post_fix"]),
            "exit_reason": result.exit_reason,
            "pnl_r": result.pnl_r,
            "pnl_quote": result.pnl_quote,
            "touched_1r": result.touched_1r,
        })
    return pd.DataFrame(rows)


def aggregate(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"n": 0}
    wins = df["pnl_r"] > 0
    pf_num = df.loc[df["pnl_r"] > 0, "pnl_r"].sum()
    pf_den = -df.loc[df["pnl_r"] < 0, "pnl_r"].sum()
    pf = pf_num / pf_den if pf_den > 0 else float("inf")
    # max DD on cumulative pnl_quote
    eq = df["pnl_quote"].cumsum()
    peak = eq.cummax()
    dd = (eq - peak)
    return {
        "n": len(df),
        "win_rate": float(wins.mean()),
        "expectancy_r": float(df["pnl_r"].mean()),
        "profit_factor": float(pf),
        "max_dd_quote": float(dd.min()),
        "pct_touched_1r": float(df["touched_1r"].mean()),
        "total_pnl_quote": float(df["pnl_quote"].sum()),
    }


def render_md(results: dict[str, pd.DataFrame], args, n_entries: int) -> str:
    md = []
    md.append(f"# Partial Exit A/B Report — {pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%M')} UTC\n")
    md.append("## Setup\n")
    md.append(f"- Entries: {n_entries} (Supabase real entries usados como semilla)")
    md.append(f"- SL_K = {args.sl_k}  TP_K = {args.tp_k}")
    md.append(f"- Fees = {args.fee_bps} bps round-trip  Slippage = {args.slip_bps} bps")
    md.append(f"- Notional por trade = ${args.notional:.0f}")
    md.append(f"- Horizonte máximo = {MAX_HORIZON_HOURS}h\n")

    md.append("## Resumen por variante × split\n")
    md.append("| Variante | Split | N | WinRate | E[R] | PF | MaxDD$ | %toca1R | Total$ |")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for v, df in results.items():
        for split_name, sub in [("ALL", df),
                                 ("PRE-FIX", df[~df["post_fix"]]),
                                 ("POST-FIX", df[df["post_fix"]])]:
            a = aggregate(sub)
            if a["n"] == 0:
                md.append(f"| {v} | {split_name} | 0 | - | - | - | - | - | - |")
                continue
            md.append(f"| {v} | {split_name} | {a['n']} | "
                      f"{a['win_rate']*100:.1f}% | {a['expectancy_r']:+.2f} | "
                      f"{a['profit_factor']:.2f} | {a['max_dd_quote']:+.2f} | "
                      f"{a['pct_touched_1r']*100:.0f}% | {a['total_pnl_quote']:+.2f} |")
    md.append("")

    md.append("## Resumen por variante × símbolo (POST-FIX only)\n")
    md.append("| Variante | Símbolo | N | WinRate | E[R] | PF | Total$ |")
    md.append("|---|---|---:|---:|---:|---:|---:|")
    for v, df in results.items():
        post = df[df["post_fix"]]
        for sym in sorted(post["symbol"].unique()):
            sub = post[post["symbol"] == sym]
            a = aggregate(sub)
            md.append(f"| {v} | {sym} | {a['n']} | "
                      f"{a['win_rate']*100:.1f}% | {a['expectancy_r']:+.2f} | "
                      f"{a['profit_factor']:.2f} | {a['total_pnl_quote']:+.2f} |")
    md.append("")

    md.append("## Distribución de exit reasons por variante (ALL)\n")
    md.append("| Variante | " + " | ".join([
        "SL", "TP", "CHANDELIER", "PARTIAL_THEN_CHANDELIER",
        "PARTIAL_THEN_END", "PARTIAL_THEN_SL", "END_OF_DATA",
    ]) + " |")
    md.append("|---|" + "---:|" * 7)
    reasons_order = ["SL", "TP", "CHANDELIER", "PARTIAL_THEN_CHANDELIER",
                      "PARTIAL_THEN_END", "PARTIAL_THEN_SL", "END_OF_DATA"]
    for v, df in results.items():
        counts = df["exit_reason"].value_counts().to_dict()
        cells = [str(counts.get(r, 0)) for r in reasons_order]
        md.append(f"| {v} | " + " | ".join(cells) + " |")
    md.append("")

    md.append("## Notas\n")
    md.append("- POST-FIX = entries posteriores al 2026-04-18 (proxy fix). "
              "Ese subset es el más confiable según drift audit.")
    md.append("- ATR computado como ATR_14 Wilder sobre 1h klines previas a entry.")
    md.append("- Conflict-bar policy: SL prioritario sobre TP en la misma vela.")
    md.append("- Horizonte máximo: 10 días por trade.")
    md.append("- CSV detalle: `02-partial-exit-ab-V*.csv`")
    return "\n".join(md)


def main() -> int:
    args = parse_args()
    out_md = Path(args.out)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    entries = pd.read_parquet(args.entries)
    entries["entry_ts"] = pd.to_datetime(entries["entry_ts"], utc=True)
    loader = KlineLoader(args.klines)
    print(f"[info] {len(entries)} entries, klines coverage: {loader.coverage()}",
          flush=True)

    results: dict[str, pd.DataFrame] = {}
    for v in VARIANTS:
        print(f"[run] variant {v}", flush=True)
        df = run_variant(v, entries, loader, args.sl_k, args.tp_k,
                          args.fee_bps, args.slip_bps, args.notional)
        results[v] = df
        # CSV per variant
        csv_path = out_md.parent / f"02-partial-exit-ab-{v}.csv"
        df.to_csv(csv_path, index=False)
        print(f"  wrote {csv_path}", flush=True)

    md = render_md(results, args, len(entries))
    out_md.write_text(md, encoding="utf-8")
    print(f"\n[done] {out_md}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
