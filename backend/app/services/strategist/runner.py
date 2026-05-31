"""Daily strategist orchestration: run the fleet → write eval markdown → propose config → notify.

The evaluation markdown is always written (primary output). The pending_approval config
insert + Telegram are best-effort. Nothing here ever touches the live (active) config.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .agent import run_strategist
from .outputs import insert_pending_config, write_evaluation
from .schemas import StrategistDecision

log = logging.getLogger(__name__)


async def run_daily_strategist() -> dict[str, Any]:
    """Run one daily strategist cycle (dry-run). Returns a summary dict."""
    run_at = datetime.now(timezone.utc).isoformat()
    decision: StrategistDecision = await run_strategist()

    eval_path = write_evaluation(decision, run_at)

    pending = None
    try:
        from ...db import get_supabase

        pending = insert_pending_config(get_supabase(), decision, run_at)
    except Exception as e:  # noqa: BLE001 — markdown is the source of truth
        log.warning("strategist pending-config insert skipped: %s", e)

    try:
        await _notify(decision, str(eval_path), pending is not None)
    except Exception:  # noqa: BLE001
        log.debug("strategist Telegram notice failed", exc_info=True)

    return {
        "decision": decision.decision,
        "confidence": decision.confidence,
        "summary": decision.summary,
        "eval_path": str(eval_path),
        "proposed_pending_config": pending is not None,
        "degraded": decision.data_quality.startswith("DEGRADED_RUN"),
    }


async def _notify(decision: StrategistDecision, eval_path: str, proposed: bool) -> None:
    from ..telegram_notifier import escape_html, send_telegram

    tag = "📝 propuesta pending" if proposed else "sin cambios"
    await send_telegram(
        f"🧠 <b>Strategist diario — {decision.decision}</b> ({tag})\n"
        f"Confianza: {decision.confidence:.0%}\n"
        f"{escape_html(decision.summary[:300])}\n\n"
        f"Eval: <code>{escape_html(eval_path.split('/')[-1].split(chr(92))[-1])}</code>"
    )
