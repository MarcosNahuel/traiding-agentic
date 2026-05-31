"""Estado durable en SQLite: órdenes pendientes, audit log, totales diarios."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_orders (
    id TEXT PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    amount REAL NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    resolved_at REAL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    tool TEXT,
    params TEXT,
    result TEXT
);
"""


class Store:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ---- Órdenes pendientes -------------------------------------------
    def create_pending(self, order_id: str, chat_id: int, payload: dict[str, Any], amount: float) -> None:
        self._conn.execute(
            "INSERT INTO pending_orders (id, chat_id, payload, status, amount, created_at)"
            " VALUES (?, ?, ?, 'pending', ?, ?)",
            (order_id, chat_id, json.dumps(payload), amount, time.time()),
        )
        self._conn.commit()

    def resolve_pending(self, order_id: str, status: str) -> None:
        self._conn.execute(
            "UPDATE pending_orders SET status = ?, resolved_at = ? WHERE id = ?",
            (status, time.time(), order_id),
        )
        self._conn.commit()

    def get_pending(self, order_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM pending_orders WHERE id = ?", (order_id,)
        ).fetchone()
        return dict(row) if row else None

    # ---- Tope diario ---------------------------------------------------
    def executed_amount_today(self) -> float:
        start = _start_of_day()
        row = self._conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS s FROM pending_orders"
            " WHERE status = 'executed' AND resolved_at >= ?",
            (start,),
        ).fetchone()
        return float(row["s"] or 0)

    def committed_amount_today(self) -> float:
        """F1 (jury): monto comprometido hoy = executed + pending (aún sin resolver).

        Contar las pending evita la race: dos órdenes confirmándose en paralelo no
        pueden superar el tope diario, porque la primera ya cuenta apenas se crea.
        """
        start = _start_of_day()
        row = self._conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS s FROM pending_orders"
            " WHERE (status = 'executed' AND resolved_at >= ?)"
            "    OR (status = 'pending'  AND created_at  >= ?)",
            (start, start),
        ).fetchone()
        return float(row["s"] or 0)

    # ---- Audit ---------------------------------------------------------
    def audit(self, kind: str, tool: str | None, params: Any, result: Any) -> None:
        self._conn.execute(
            "INSERT INTO audit (ts, kind, tool, params, result) VALUES (?, ?, ?, ?, ?)",
            (time.time(), kind, tool, json.dumps(params, default=str), json.dumps(result, default=str)),
        )
        self._conn.commit()


def _start_of_day() -> float:
    now = time.localtime()
    return time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, -1))
