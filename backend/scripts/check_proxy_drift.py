"""Phase 0.1 — Proxy drift check.

Reads recent SL/TP-triggered trades from Supabase, compares trigger_price vs
executed price, reports drift.

Pass criteria: >90% of last N trades have abs(drift) < 1%.

Usage: python scripts/check_proxy_drift.py [--limit 20]
"""

import argparse
import asyncio
import json

from app.db import get_supabase


async def main(limit: int = 20):
    supabase = get_supabase()

    # Fetch last N closed positions with stop_loss_price set
    resp = (
        supabase.table("positions")
        .select("id,symbol,entry_price,stop_loss_price,exit_price,realized_pnl_percent,closed_at,close_reason")
        .eq("status", "closed")
        .not_.is_("stop_loss_price", "null")
        .not_.is_("exit_price", "null")
        .order("closed_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        print(json.dumps({"error": "no closed trades"}))
        return 1

    drifts = []
    for r in rows:
        sl = float(r.get("stop_loss_price") or 0)
        ex = float(r.get("exit_price") or 0)
        if sl <= 0 or ex <= 0:
            continue
        pct = abs(sl - ex) / ex * 100.0
        drifts.append({
            "symbol": r["symbol"],
            "sl": sl,
            "exit": ex,
            "drift_pct": round(pct, 3),
            "close_reason": r.get("close_reason"),
            "closed_at": r.get("closed_at"),
        })

    over_1pct = [d for d in drifts if d["drift_pct"] > 1.0]
    pct_over = len(over_1pct) / max(1, len(drifts)) * 100.0
    passed = pct_over <= 10.0  # <=10% over 1% drift = >=90% under 1%

    out = {
        "n_trades": len(drifts),
        "n_over_1pct": len(over_1pct),
        "pct_over_1pct": round(pct_over, 1),
        "passed": passed,
        "trades": drifts,
    }
    print(json.dumps(out, indent=2, default=str))
    return 0 if passed else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.limit)))
