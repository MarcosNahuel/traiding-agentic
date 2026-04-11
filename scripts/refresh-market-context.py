#!/usr/bin/env python3
"""Regenera docs/knowledge-base/current-market.md con snapshot actual.

Uso:
    python scripts/refresh-market-context.py

Requiere env:
    NEXT_PUBLIC_SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "docs" / "knowledge-base" / "current-market.md"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for candidate in (".env.local", ".env"):
        p = REPO_ROOT / candidate
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k not in env:
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k not in env})
    return env


def supabase_get(base_url: str, key: str, path: str, query: str = "") -> list | dict:
    url = f"{base_url}/rest/v1/{path}"
    if query:
        url += f"?{query}"
    req = urllib.request.Request(url, headers={
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_snapshot(positions: list, proposals: list) -> str:
    now = datetime.now(timezone.utc)
    closed = [p for p in positions if p["status"] == "closed"]
    opened = [p for p in positions if p["status"] == "open"]

    # Últimos 7 días
    week_ago = now.timestamp() - 7 * 86400
    recent = []
    for p in closed:
        if not p.get("closed_at"):
            continue
        ts = datetime.fromisoformat(p["closed_at"].replace("Z", "+00:00")).timestamp()
        if ts >= week_ago:
            recent.append(p)

    total_pnl = sum((p.get("realized_pnl") or 0) for p in closed)
    recent_pnl = sum((p.get("realized_pnl") or 0) for p in recent)
    wins = [p for p in closed if (p.get("realized_pnl") or 0) > 0]
    losses = [p for p in closed if (p.get("realized_pnl") or 0) < 0]

    recent_wins = [p for p in recent if (p.get("realized_pnl") or 0) > 0]
    recent_losses = [p for p in recent if (p.get("realized_pnl") or 0) < 0]

    def safe_pf(w, l):
        gw = sum(x.get("realized_pnl") or 0 for x in w)
        gl = abs(sum(x.get("realized_pnl") or 0 for x in l))
        return gw / gl if gl > 0 else float("inf") if gw > 0 else 0

    # Por símbolo últimos 7 días
    by_symbol: dict[str, dict] = defaultdict(lambda: {"pnl": 0.0, "count": 0, "wins": 0})
    for p in recent:
        s = p["symbol"]
        by_symbol[s]["pnl"] += p.get("realized_pnl") or 0
        by_symbol[s]["count"] += 1
        if (p.get("realized_pnl") or 0) > 0:
            by_symbol[s]["wins"] += 1

    # Últimos exit reasons
    exit_tags: dict[str, int] = defaultdict(int)
    for pr in proposals:
        if pr.get("type") != "sell":
            continue
        r = pr.get("reasoning") or ""
        if r.startswith("["):
            tag = r.split("]")[0] + "]"
            exit_tags[tag] += 1

    lines: list[str] = []
    lines.append("---")
    lines.append(f"generated_at: {now.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("stale_after: 1 hour")
    lines.append("---")
    lines.append("")
    lines.append("# Current Market Snapshot")
    lines.append("")
    lines.append("> Este archivo se genera con `python scripts/refresh-market-context.py`.")
    lines.append("> Si el timestamp tiene >1 hora, regenerar antes de reevaluar la estrategia.")
    lines.append("")

    lines.append("## Estado de posiciones")
    lines.append("")
    lines.append(f"- **Abiertas:** {len(opened)}")
    lines.append(f"- **Cerradas histórico:** {len(closed)}")
    lines.append(f"- **P&L total histórico:** ${total_pnl:.2f}")
    lines.append("")

    if opened:
        lines.append("### Posiciones actualmente abiertas")
        lines.append("")
        lines.append("| Symbol | Side | Entry | SL | TP | Abierta hace |")
        lines.append("|---|---|---|---|---|---|")
        for p in opened:
            opened_at = p.get("opened_at", "")
            try:
                opened_dt = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
                age_h = (now - opened_dt).total_seconds() / 3600
                age_str = f"{age_h:.1f} h"
            except Exception:
                age_str = "?"
            lines.append(
                f"| {p['symbol']} | {p['side']} | ${p.get('entry_price','?')} "
                f"| ${p.get('stop_loss_price','?')} | ${p.get('take_profit_price','?')} | {age_str} |"
            )
        lines.append("")

    lines.append("## Últimos 7 días")
    lines.append("")
    lines.append(f"- **Trades cerrados:** {len(recent)}")
    lines.append(f"- **P&L:** ${recent_pnl:+.2f}")
    if recent:
        wr = len(recent_wins) / len(recent) * 100
        lines.append(f"- **Win rate:** {wr:.1f}% ({len(recent_wins)}W / {len(recent_losses)}L)")
        lines.append(f"- **Profit factor:** {safe_pf(recent_wins, recent_losses):.2f}")
    lines.append("")

    if by_symbol:
        lines.append("### Por símbolo (7d)")
        lines.append("")
        lines.append("| Symbol | P&L | Trades | Win Rate |")
        lines.append("|---|---|---|---|")
        for s, d in sorted(by_symbol.items(), key=lambda x: -x[1]["pnl"]):
            wr = d["wins"] / d["count"] * 100 if d["count"] else 0
            lines.append(f"| {s} | ${d['pnl']:+.2f} | {d['count']} | {wr:.0f}% |")
        lines.append("")

    if exit_tags:
        total = sum(exit_tags.values())
        lines.append("### Motivos de cierre (últimas 200 proposals)")
        lines.append("")
        lines.append("| Tag | Count | % |")
        lines.append("|---|---|---|")
        for tag, count in sorted(exit_tags.items(), key=lambda x: -x[1]):
            lines.append(f"| {tag} | {count} | {count/total*100:.0f}% |")
        lines.append("")

    # Red flags
    lines.append("## Red Flags (auto-check)")
    lines.append("")
    flags: list[str] = []
    if total_pnl < -20:
        flags.append(f"🚨 Drawdown total ${total_pnl:.2f} < -$20")
    if recent and len(recent) >= 10:
        wr = len(recent_wins) / len(recent) * 100
        if wr < 40:
            flags.append(f"🚨 Win rate 7d {wr:.0f}% < 40%")
        pf = safe_pf(recent_wins, recent_losses)
        if 0 < pf < 0.8:
            flags.append(f"🚨 Profit factor 7d {pf:.2f} < 0.8")
    if not flags:
        lines.append("✓ Ninguna red flag detectada")
    else:
        for f in flags:
            lines.append(f"- {f}")
    lines.append("")

    lines.append("## Checklist de reevaluación")
    lines.append("")
    lines.append("- [ ] Leer `decision-matrix.md`")
    lines.append("- [ ] Verificar régimen actual del símbolo (si hay posición abierta)")
    lines.append("- [ ] Revisar last evaluation en `evaluations/`")
    lines.append("- [ ] Si hay red flags → acción inmediata")
    lines.append("- [ ] Guardar nueva evaluation en `evaluations/YYYY-MM-DD-HHMM.md`")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    env = load_env()
    url = env.get("NEXT_PUBLIC_SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: falta NEXT_PUBLIC_SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
        return 1

    try:
        positions = supabase_get(
            url, key, "positions",
            "select=symbol,side,status,entry_price,exit_price,stop_loss_price,take_profit_price,"
            "realized_pnl,realized_pnl_percent,opened_at,closed_at&order=opened_at.desc&limit=500",
        )
        proposals = supabase_get(
            url, key, "trade_proposals",
            "select=symbol,type,reasoning,created_at,status&status=eq.executed&order=created_at.desc&limit=200",
        )
    except Exception as e:
        print(f"ERROR: Supabase query failed: {e}", file=sys.stderr)
        return 1

    content = build_snapshot(positions, proposals)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(REPO_ROOT)} ({len(content)} chars)")
    print(f"Positions: {len(positions)} | Proposals: {len(proposals)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
