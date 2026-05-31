"""Aprobación de propuestas del strategist — cierra el loop:
Claude propone (pending_approval) → humano confirma por Telegram → bot adapta (active).

promote_latest_pending: la última pending pasa a active (supersede la active anterior).
reject_latest_pending: la última pending pasa a rejected (NUNCA toca la active).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger(__name__)


def _latest_pending(supabase: Any) -> Optional[dict]:
    resp = (
        supabase.table("llm_trading_configs")
        .select("*")
        .eq("status", "pending_approval")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def promote_latest_pending(supabase: Any) -> Optional[dict]:
    """Promueve la última config pending_approval a active. Devuelve la config o None."""
    cfg = _latest_pending(supabase)
    if not cfg:
        return None
    now = datetime.now(timezone.utc).isoformat()
    # Desactivar la active vigente (puede no haber ninguna).
    supabase.table("llm_trading_configs").update(
        {"status": "superseded", "superseded_at": now}
    ).eq("status", "active").execute()
    # Promover la pending elegida.
    supabase.table("llm_trading_configs").update(
        {"status": "active", "approved_at": now}
    ).eq("id", cfg["id"]).execute()
    # Que el bot la tome ya (sin esperar el TTL de cache de 60s).
    try:
        from ..daily_analyst.config_bridge import invalidate_cache

        invalidate_cache()
    except Exception:  # noqa: BLE001
        pass
    log.info("strategist config %s promovida a active", cfg.get("id"))
    return cfg


def reject_latest_pending(supabase: Any) -> Optional[dict]:
    """Marca la última config pending_approval como rejected. Nunca toca la active."""
    cfg = _latest_pending(supabase)
    if not cfg:
        return None
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("llm_trading_configs").update(
        {"status": "rejected", "rejected_at": now}
    ).eq("id", cfg["id"]).execute()
    log.info("strategist config %s rechazada", cfg.get("id"))
    return cfg
