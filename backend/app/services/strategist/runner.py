"""Daily strategist orchestration: run the fleet → write eval markdown → propose config → notify.

The evaluation markdown is always written (primary output). The pending_approval config
insert + Telegram are best-effort. Nothing here ever touches the live (active) config.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .agent import run_strategist
from .outputs import insert_pending_config, write_evaluation, write_report_event
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

        supabase = get_supabase()
        # Persistir el informe del día para el dashboard (toda corrida).
        write_report_event(supabase, decision, run_at)
        pending = insert_pending_config(supabase, decision, run_at)
    except Exception as e:  # noqa: BLE001 — markdown is the source of truth
        log.warning("strategist supabase write skipped: %s", e)

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
    from ...config import settings
    from ..telegram_notifier import escape_html, send_telegram

    msg = (
        f"🧠 <b>Strategist diario — {decision.decision}</b>\n"
        f"Confianza: {decision.confidence:.0%}\n"
        f"{escape_html(decision.summary[:420])}\n"
    )
    if proposed and settings.strategist_approval_token:
        base = settings.bot_public_url.rstrip("/")
        tok = settings.strategist_approval_token
        msg += (
            f"\n📝 <b>Propone cambiar la config.</b> Confirmá tocando un link:\n"
            f"✅ Aprobar: {base}/strategist/approve?token={tok}\n"
            f"❌ Rechazar: {base}/strategist/reject?token={tok}"
        )
    elif proposed:
        msg += "\n📝 Propuesta pending (falta STRATEGIST_APPROVAL_TOKEN para el link de aprobación)."
    await send_telegram(msg)
