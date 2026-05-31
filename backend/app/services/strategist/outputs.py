"""Strategist outputs: write the daily evaluation markdown + (dry-run) propose a config.

DRY-RUN SAFETY (the whole point): insert_pending_config may ONLY write
status='pending_approval'. It must NEVER write status='active' nor supersede the
live config. A human promotes the proposal via the approval flow.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .schemas import StrategistDecision

log = logging.getLogger(__name__)

# backend/app/services/strategist/outputs.py → parents[4] == repo root
_DEFAULT_EVAL_DIR = Path(__file__).resolve().parents[4] / "docs" / "knowledge-base" / "evaluations"


def write_evaluation(
    decision: StrategistDecision, run_at_iso: str, evaluations_dir: Path | str = _DEFAULT_EVAL_DIR
) -> Path:
    """Write the daily strategist evaluation markdown. This is the primary, durable output."""
    d = Path(evaluations_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{run_at_iso[:10]}-strategist.md"
    path.write_text(decision.render_markdown(run_at_iso), encoding="utf-8")
    log.info("strategist evaluation written: %s", path)
    return path


def insert_pending_config(
    supabase: Any, decision: StrategistDecision, run_at_iso: str
) -> Optional[dict]:
    """Insert a pending_approval config row — ONLY for TWEAK_PARAMS. Never active, never supersede.

    Returns the inserted row payload, or None when there is nothing to propose.
    Fail-safe: never raises into the run.
    """
    if decision.decision != "TWEAK_PARAMS":
        return None  # KEEP / PROPOSE_STRATEGY_CHANGE / RECOMMEND_PAUSE → markdown only

    clamped, warnings = decision.clamped_config()
    if not clamped:
        return None

    now = datetime.now(timezone.utc)
    expires = (now.replace(hour=23, minute=0, second=0, microsecond=0) + timedelta(days=1))
    row = {
        **clamped,
        "status": "pending_approval",   # NEVER 'active' — dry-run guarantee
        "proposed_by": "strategist",
        "source": "strategist",
        "reasoning": decision.summary,
        "confidence_score": decision.confidence,
        "values_clamped": warnings,
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
    }
    try:
        supabase.table("llm_trading_configs").insert(row).execute()
        log.info("strategist proposed pending_approval config: %s", decision.summary[:80])
    except Exception as e:  # noqa: BLE001 — best-effort; markdown is the source of truth
        log.warning("pending config insert failed (markdown still written): %s", e)
    return row
