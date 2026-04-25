"""Drift audit: cross-check Supabase trade exits vs Binance Live klines.

Detects "ghost SL" — cases where the recorded exit_price implies an SL
trigger that didn't actually happen on the Binance side (proxy stale).

Usage:
    python -m backend.scripts.diagnostics.02_drift_audit \
        --trades data/diagnostics/trades.csv \
        --klines data/diagnostics/klines.parquet \
        --fix-date 2026-04-18 \
        --out backend/scripts/diagnostics/reports/01-drift-audit.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to sys.path so we can import the lib package as
# `backend.scripts.diagnostics.lib...` regardless of how the script is invoked.
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.scripts.diagnostics.lib.kline_loader import KlineLoader  # noqa: E402

GHOST_DRIFT_BPS = 30.0  # |drift| > 30 bps and direction-mismatched = ghost
EXIT_REASON_TOLERANCE_PCT = 0.005  # 0.5% — match exit_price to SL/TP


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trades", default="data/diagnostics/trades.csv")
    p.add_argument("--klines", default="data/diagnostics/klines.parquet")
    p.add_argument("--fix-date", default="2026-04-18",
                   help="ISO date that splits 'before fix' vs 'after fix'")
    p.add_argument("--out", default="backend/scripts/diagnostics/reports/01-drift-audit.md")
    p.add_argument("--ghost-bps", type=float, default=GHOST_DRIFT_BPS)
    return p.parse_args()


def derive_exit_reason(row: pd.Series, tol_pct: float = EXIT_REASON_TOLERANCE_PCT) -> str:
    """Heuristic: if exit_price ~= SL → SL; ~= TP → TP; else MANUAL."""
    exit_p = row["exit_price"]
    sl = row.get("stop_loss_price")
    tp = row.get("take_profit_price")
    if pd.notna(sl) and abs(exit_p - sl) / sl <= tol_pct:
        return "STOP_LOSS"
    if pd.notna(tp) and abs(exit_p - tp) / tp <= tol_pct:
        return "TAKE_PROFIT"
    return "MANUAL_OR_TRAIL"


def compute_drift_bps(exit_p: float, kline_close: float) -> float:
    """Drift in basis points: (exit_p - kline_close) / kline_close * 10_000."""
    return (exit_p - kline_close) / kline_close * 10_000.0


def is_ghost_sl(side: str, exit_p: float, sl_p: float | None,
                kline_low: float, kline_high: float,
                kline_close: float, ghost_bps: float) -> bool:
    """A 'ghost SL' is one where:
    - the exit was an SL according to the price match
    - the actual binance kline (low for long, high for short) never reached the SL
    - and the |drift| exceeds the threshold
    """
    if pd.isna(sl_p) or pd.isna(kline_low) or pd.isna(kline_high):
        return False
    drift = compute_drift_bps(exit_p, kline_close)
    if abs(drift) <= ghost_bps:
        return False
    if side == "long":
        # Real SL hit means binance low <= sl_p. Ghost = it didn't reach.
        return kline_low > sl_p
    else:
        return kline_high < sl_p


def histogram_bins(s: pd.Series) -> dict[str, int]:
    bins = [0, 5, 10, 20, 30, 50, 100, np.inf]
    labels = ["0-5", "5-10", "10-20", "20-30", "30-50", "50-100", ">100"]
    cuts = pd.cut(s.abs(), bins=bins, labels=labels, include_lowest=True)
    return cuts.value_counts().reindex(labels, fill_value=0).to_dict()


def render_report(rows: pd.DataFrame, fix_date: pd.Timestamp,
                  ghost_bps: float, out_path: Path) -> str:
    n = len(rows)
    valid = rows[rows["binance_close"].notna()]
    sl_rows = valid[valid["derived_exit_reason"] == "STOP_LOSS"]
    tp_rows = valid[valid["derived_exit_reason"] == "TAKE_PROFIT"]

    n_ghost = int(valid["ghost_sl"].sum())
    pct_ghost = n_ghost / max(len(sl_rows), 1) * 100.0

    pre = valid[valid["closed_at"] < fix_date]
    post = valid[valid["closed_at"] >= fix_date]
    pre_sl = pre[pre["derived_exit_reason"] == "STOP_LOSS"]
    post_sl = post[post["derived_exit_reason"] == "STOP_LOSS"]
    pre_ghost_pct = (pre_sl["ghost_sl"].sum() / max(len(pre_sl), 1)) * 100.0
    post_ghost_pct = (post_sl["ghost_sl"].sum() / max(len(post_sl), 1)) * 100.0

    # Verdict
    if len(post_sl) < 5:
        verdict = (f"INCONCLUSO — sólo {len(post_sl)} SL después del fix "
                   f"({fix_date.date()}). Se necesita más muestra.")
    elif pre_ghost_pct > 20.0 and post_ghost_pct < 5.0:
        verdict = (f"FIX FUNCIONÓ — ghost SL bajaron de {pre_ghost_pct:.1f}% "
                   f"a {post_ghost_pct:.1f}% después de {fix_date.date()}.")
    elif post_ghost_pct >= pre_ghost_pct - 5:
        verdict = (f"FIX **NO** FUNCIONÓ — ghost SL siguen en {post_ghost_pct:.1f}% "
                   f"(eran {pre_ghost_pct:.1f}%). Escalar antes de seguir.")
    else:
        verdict = (f"MEJORÓ PARCIAL — ghost SL: {pre_ghost_pct:.1f}% → "
                   f"{post_ghost_pct:.1f}%. Revisar si es suficiente.")

    pre_hist = histogram_bins(pre["drift_bps"])
    post_hist = histogram_bins(post["drift_bps"])

    md = []
    md.append(f"# Drift Audit Report — {pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%M')} UTC\n")
    md.append("## Resumen ejecutivo\n")
    md.append(f"- **Trades totales**: {n}")
    md.append(f"- **Trades con kline disponible**: {len(valid)}")
    md.append(f"- **SL detectados (heurística exit_price≈SL)**: {len(sl_rows)}")
    md.append(f"- **TP detectados**: {len(tp_rows)}")
    md.append(f"- **Ghost SL totales** (|drift| > {ghost_bps:.0f} bps Y kline no tocó SL): "
              f"**{n_ghost}** ({pct_ghost:.1f}% de SL)")
    md.append(f"- **Fecha del fix**: {fix_date.date()}")
    md.append(f"- **Ghost SL antes del fix**: {pre_sl['ghost_sl'].sum()}/{len(pre_sl)} "
              f"({pre_ghost_pct:.1f}%)")
    md.append(f"- **Ghost SL después del fix**: {post_sl['ghost_sl'].sum()}/{len(post_sl)} "
              f"({post_ghost_pct:.1f}%)\n")
    md.append(f"## Veredicto\n\n**{verdict}**\n")

    md.append("## Histograma |drift_bps|\n")
    md.append("| Bin | Pre-fix | Post-fix |")
    md.append("|---|---:|---:|")
    for k in pre_hist:
        md.append(f"| {k} | {pre_hist[k]} | {post_hist[k]} |")
    md.append("")

    md.append("## Top 20 trades por |drift_bps|\n")
    top = valid.assign(absdrift=valid["drift_bps"].abs()) \
               .sort_values("absdrift", ascending=False).head(20)
    md.append("| symbol | side | closed_at | exit_reason | exit_price | binance_close | drift_bps | ghost? |")
    md.append("|---|---|---|---|---:|---:|---:|---:|")
    for _, r in top.iterrows():
        md.append(f"| {r['symbol']} | {r['side']} | "
                  f"{r['closed_at'].strftime('%Y-%m-%d %H:%M')} | "
                  f"{r['derived_exit_reason']} | {r['exit_price']:.2f} | "
                  f"{r['binance_close']:.2f} | {r['drift_bps']:+.1f} | "
                  f"{'YES' if r['ghost_sl'] else ''} |")
    md.append("")

    md.append("## Notas\n")
    md.append(f"- El umbral ghost = |drift_bps| > {ghost_bps:.0f} (≈{ghost_bps/100:.2f}%) "
              "Y la kline real no contiene el SL.")
    md.append("- `derived_exit_reason` se computa con tolerancia "
              f"{EXIT_REASON_TOLERANCE_PCT*100:.1f}% sobre exit_price vs SL/TP.")
    md.append("- Klines = Binance Live spot (públicas), tf 1m.")
    md.append("- CSV detalle adjunto: `01-drift-audit.csv`")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(md), encoding="utf-8")
    return verdict


def main() -> int:
    args = parse_args()
    out_md = Path(args.out)
    out_csv = out_md.with_suffix(".csv")

    trades = pd.read_csv(args.trades)
    trades["opened_at"] = pd.to_datetime(trades["opened_at"], utc=True)
    trades["closed_at"] = pd.to_datetime(trades["closed_at"], utc=True)
    fix_date = pd.Timestamp(args.fix_date, tz="UTC")

    loader = KlineLoader(args.klines)

    rows: list[dict] = []
    for _, t in trades.iterrows():
        kl = loader.kline_at(t["symbol"], "1m", t["closed_at"])
        record = {
            "id": t["id"],
            "symbol": t["symbol"],
            "side": t["side"],
            "opened_at": t["opened_at"],
            "closed_at": t["closed_at"],
            "exit_price": float(t["exit_price"]),
            "stop_loss_price": float(t["stop_loss_price"]) if pd.notna(t["stop_loss_price"]) else np.nan,
            "take_profit_price": float(t["take_profit_price"]) if pd.notna(t["take_profit_price"]) else np.nan,
            "binance_close": float(kl["close"]) if kl is not None else np.nan,
            "binance_low": float(kl["low"]) if kl is not None else np.nan,
            "binance_high": float(kl["high"]) if kl is not None else np.nan,
        }
        record["drift_bps"] = (compute_drift_bps(record["exit_price"], record["binance_close"])
                                if kl is not None else np.nan)
        record["derived_exit_reason"] = derive_exit_reason(t)
        record["ghost_sl"] = (record["derived_exit_reason"] == "STOP_LOSS"
                               and is_ghost_sl(t["side"], record["exit_price"],
                                                record["stop_loss_price"],
                                                record["binance_low"],
                                                record["binance_high"],
                                                record["binance_close"],
                                                args.ghost_bps))
        rows.append(record)

    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)
    verdict = render_report(df, fix_date, args.ghost_bps, out_md)
    print(f"\n{verdict}\n")
    print(f"Wrote: {out_md}")
    print(f"Wrote: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
