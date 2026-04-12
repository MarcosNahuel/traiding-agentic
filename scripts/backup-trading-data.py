#!/usr/bin/env python3
"""Backup full trading data from Supabase to local CSV for ML training.

Usage:
    python scripts/backup-trading-data.py [--date YYYY-MM-DD]

Exports to: data/ml_backup/YYYY-MM-DD/{table}.csv
"""
from __future__ import annotations

import csv
import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGE_SIZE = 1000

TABLES = [
    ("positions", "id", "opened_at"),
    ("trade_proposals", "id", "created_at"),
    ("risk_events", "id", "created_at"),
    ("klines_ohlcv", "id", "open_time"),
    ("technical_indicators", "id", "created_at"),
    ("reconciliation_runs", "id", "created_at"),
    ("orders", "id", "updated_at"),
    ("account_snapshots", "id", "created_at"),
    ("market_regimes", "id", "created_at"),
    ("support_resistance_levels", "id", "created_at"),
    ("entropy_readings", "id", "created_at"),
    ("backtest_results", "id", "created_at"),
]


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
            if k not in env and v:
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k not in env})
    return env


def supabase_fetch_all(base_url: str, key: str, table: str, order_col: str) -> list[dict]:
    results: list[dict] = []
    offset = 0
    while True:
        params = {
            "select": "*",
            "order": f"{order_col}.asc",
            "limit": str(PAGE_SIZE),
            "offset": str(offset),
        }
        url = f"{base_url}/rest/v1/{table}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                page = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"    ERROR fetching {table}: {e}")
            return results
        if not page:
            break
        results.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return results


def write_csv(path: Path, rows: list[dict]) -> int:
    if not rows:
        path.write_text("", encoding="utf-8")
        return 0
    keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in rows:
            flat = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in r.items()}
            writer.writerow(flat)
    return path.stat().st_size


def main() -> int:
    env = load_env()
    url = env.get("NEXT_PUBLIC_SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: falta NEXT_PUBLIC_SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
        return 1

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for arg in sys.argv[1:]:
        if arg.startswith("--date="):
            date_str = arg.split("=", 1)[1]

    out_dir = REPO_ROOT / "data" / "ml_backup" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Backup destination: {out_dir.relative_to(REPO_ROOT)}")
    print()

    manifest: dict[str, dict] = {}
    total_bytes = 0
    total_rows = 0
    for table, _pk, order_col in TABLES:
        print(f"  [{table}] fetching...", end=" ", flush=True)
        rows = supabase_fetch_all(url, key, table, order_col)
        path = out_dir / f"{table}.csv"
        size = write_csv(path, rows)
        manifest[table] = {"rows": len(rows), "bytes": size}
        total_bytes += size
        total_rows += len(rows)
        print(f"{len(rows):>7,} rows, {size/1024:>8.1f} KB")

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps({
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "supabase_url": url,
        "tables": manifest,
        "total_rows": total_rows,
        "total_bytes": total_bytes,
    }, indent=2), encoding="utf-8")

    print()
    print(f"Total: {total_rows:,} rows, {total_bytes/1024/1024:.2f} MB")
    print(f"Manifest: {manifest_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
