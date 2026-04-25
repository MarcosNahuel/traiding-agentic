"""Read-only snapshot del estado actual del bot — trades recientes,
posiciones abiertas, risk events, último account snapshot.

Usage:
    python -m backend.scripts.diagnostics.check_trading_status
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env", override=False)

URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
if not URL or not KEY:
    sys.exit("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

sb = create_client(URL, KEY)

now = datetime.now(timezone.utc)
since_24h = (now - timedelta(hours=24)).isoformat()
since_7d = (now - timedelta(days=7)).isoformat()
since_fix = "2026-04-18T00:00:00+00:00"


def hr(title: str) -> None:
    print(f"\n{'='*60}\n  {title}\n{'='*60}")


# ---- Open positions ----
hr("POSICIONES ABIERTAS")
res = sb.table("positions").select(
    "id,symbol,side,opened_at,entry_price,current_price,"
    "stop_loss_price,take_profit_price,unrealized_pnl,unrealized_pnl_percent,"
    "partial_exit_taken"
).eq("status", "open").order("opened_at", desc=True).execute()
if not res.data:
    print("  (ninguna)")
else:
    for p in res.data:
        print(f"  • {p['symbol']:8} {p['side']:5}  entry={float(p['entry_price']):.2f}  "
              f"current={float(p['current_price'] or 0):.2f}  "
              f"SL={float(p['stop_loss_price'] or 0):.2f}  "
              f"TP={float(p['take_profit_price'] or 0):.2f}  "
              f"uPnL={float(p['unrealized_pnl'] or 0):+.2f} "
              f"({float(p['unrealized_pnl_percent'] or 0):+.2f}%)  "
              f"partial={p['partial_exit_taken']}  opened={p['opened_at'][:16]}")

# ---- Trades cerrados últimas 24h ----
hr("TRADES CERRADOS — ÚLTIMAS 24h")
res = sb.table("positions").select(
    "symbol,side,opened_at,closed_at,entry_price,exit_price,"
    "realized_pnl,realized_pnl_percent"
).eq("status", "closed").gte("closed_at", since_24h).order("closed_at", desc=True).execute()
if not res.data:
    print("  (ninguno)")
else:
    total = 0.0
    for p in res.data:
        pnl = float(p["realized_pnl"] or 0)
        total += pnl
        print(f"  • {p['symbol']:8} {p['side']:5}  "
              f"entry={float(p['entry_price']):.2f} → exit={float(p['exit_price']):.2f}  "
              f"PnL={pnl:+.2f} ({float(p['realized_pnl_percent'] or 0):+.2f}%)  "
              f"closed={p['closed_at'][:16]}")
    print(f"  ──────  Total 24h: ${total:+.2f}  ({len(res.data)} trades)")

# ---- Resumen post-fix (desde 2026-04-18) ----
hr(f"RESUMEN POST-FIX (desde {since_fix[:10]})")
res = sb.table("positions").select("realized_pnl,realized_pnl_percent,symbol").eq(
    "status", "closed").gte("closed_at", since_fix).execute()
if not res.data:
    print("  (ninguno)")
else:
    pnls = [float(r["realized_pnl"] or 0) for r in res.data]
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    by_sym: dict[str, list[float]] = {}
    for r in res.data:
        by_sym.setdefault(r["symbol"], []).append(float(r["realized_pnl"] or 0))
    print(f"  N trades:         {len(pnls)}")
    print(f"  Wins / Losses:    {wins} / {losses}")
    print(f"  Win rate:         {wins/len(pnls)*100:.1f}%")
    print(f"  P&L total:        ${sum(pnls):+.2f}")
    print(f"  P&L promedio:     ${sum(pnls)/len(pnls):+.2f}")
    print(f"  Mejor / peor:     ${max(pnls):+.2f} / ${min(pnls):+.2f}")
    print()
    print("  Por símbolo:")
    for sym, pl in by_sym.items():
        print(f"    {sym:8}  N={len(pl):2}  total=${sum(pl):+7.2f}  avg=${sum(pl)/len(pl):+.2f}")

# ---- Risk events últimas 24h ----
hr("RISK EVENTS — ÚLTIMAS 24h")
res = sb.table("risk_events").select("*").gte(
    "created_at", since_24h).order("created_at", desc=True).limit(15).execute()
if not res.data:
    print("  (ninguno)")
else:
    for e in res.data:
        sev = (e.get("severity") or "").upper()
        et = e.get("event_type") or e.get("type") or "?"
        desc = (e.get("description") or e.get("message") or "")[:80]
        print(f"  [{sev}] {et:25} {desc}  ({e.get('created_at', '')[:16]})")
    print(f"  Total: {len(res.data)} events (mostrando primeros 15)")

# ---- Trade proposals últimas 24h ----
hr("TRADE PROPOSALS — ÚLTIMAS 24h")
res = sb.table("trade_proposals").select("*").gte(
    "created_at", since_24h).order("created_at", desc=True).limit(20).execute()
if not res.data:
    print("  (ninguna)")
else:
    by_status: dict[str, int] = {}
    for r in res.data:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    print(f"  Total: {len(res.data)}")
    for s, n in by_status.items():
        print(f"    {s}: {n}")

# ---- Account snapshot ----
hr("ÚLTIMO ACCOUNT SNAPSHOT")
res = sb.table("account_snapshots").select("*").order("created_at", desc=True).limit(1).execute()
if not res.data:
    print("  (ninguno)")
else:
    s = res.data[0]
    print(f"  Fecha:        {s.get('created_at', '')[:16]}")
    for k, v in s.items():
        if k in ("id", "created_at", "raw_account_info"):
            continue
        print(f"  {k:25} {v}")

print()
