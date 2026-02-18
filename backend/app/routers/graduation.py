"""Graduation check — evaluates if the system is ready for live trading.

Criteria:
1. 7 days stable (>100 reconciliation runs, <1% errors)
2. Sharpe > 0
3. Error rate < 1% in proposals
4. No divergences for 48h
5. No pending dead-letters
"""

from fastapi import APIRouter
from datetime import datetime, timezone, timedelta
from ..db import get_supabase
import logging
import math

router = APIRouter(prefix="/graduation", tags=["graduation"])
logger = logging.getLogger(__name__)


@router.get("/check")
async def graduation_check():
    supabase = get_supabase()
    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    forty_eight_hours_ago = (now - timedelta(hours=48)).isoformat()

    criteria = {}

    # 1. Stability: >100 recon runs in 7 days, <1% error rate in recon
    try:
        recon_resp = supabase.table("reconciliation_runs").select(
            "id, status", count="exact"
        ).gte("created_at", seven_days_ago).execute()
        total_recons = recon_resp.count or 0
        error_recons = sum(1 for r in (recon_resp.data or []) if r["status"] == "error")
        recon_error_rate = (error_recons / total_recons * 100) if total_recons > 0 else 100

        criteria["stability"] = {
            "pass": total_recons >= 100 and recon_error_rate < 1,
            "recon_runs_7d": total_recons,
            "recon_error_rate": round(recon_error_rate, 2),
            "required": ">= 100 runs, < 1% error rate",
        }
    except Exception as e:
        criteria["stability"] = {"pass": False, "error": str(e)}

    # 2. Sharpe > 0 (simplified: based on daily PnL from closed positions)
    try:
        positions_resp = supabase.table("positions").select(
            "realized_pnl, closed_at"
        ).eq("status", "closed").gte("closed_at", seven_days_ago).execute()
        closed = positions_resp.data or []

        if len(closed) >= 2:
            pnls = [float(p["realized_pnl"]) for p in closed if p.get("realized_pnl") is not None]
            if pnls:
                mean_pnl = sum(pnls) / len(pnls)
                variance = sum((x - mean_pnl) ** 2 for x in pnls) / len(pnls)
                std_pnl = math.sqrt(variance) if variance > 0 else 0.001
                sharpe = mean_pnl / std_pnl if std_pnl > 0 else 0
            else:
                sharpe = 0
        else:
            sharpe = 0

        criteria["sharpe"] = {
            "pass": sharpe > 0,
            "value": round(sharpe, 4),
            "trades_analyzed": len(closed),
            "required": "> 0",
        }
    except Exception as e:
        criteria["sharpe"] = {"pass": False, "error": str(e)}

    # 3. Proposal error rate < 1%
    try:
        all_proposals_resp = supabase.table("trade_proposals").select(
            "id, status", count="exact"
        ).gte("created_at", seven_days_ago).execute()
        total_proposals = all_proposals_resp.count or 0
        error_proposals = sum(
            1 for p in (all_proposals_resp.data or [])
            if p["status"] in ("error", "dead_letter")
        )
        proposal_error_rate = (error_proposals / total_proposals * 100) if total_proposals > 0 else 0

        criteria["proposal_error_rate"] = {
            "pass": proposal_error_rate < 1 and total_proposals > 0,
            "rate": round(proposal_error_rate, 2),
            "total": total_proposals,
            "errors": error_proposals,
            "required": "< 1%",
        }
    except Exception as e:
        criteria["proposal_error_rate"] = {"pass": False, "error": str(e)}

    # 4. No divergences for 48h
    try:
        recent_recon_resp = supabase.table("reconciliation_runs").select(
            "id, divergences_found"
        ).gte("created_at", forty_eight_hours_ago).execute()
        recent_divergences = sum(
            r.get("divergences_found", 0) for r in (recent_recon_resp.data or [])
        )
        criteria["no_divergences_48h"] = {
            "pass": recent_divergences == 0,
            "divergences_48h": recent_divergences,
            "required": "0 divergences in last 48 hours",
        }
    except Exception as e:
        criteria["no_divergences_48h"] = {"pass": False, "error": str(e)}

    # 5. No pending dead-letters
    try:
        dl_resp = supabase.table("trade_proposals").select(
            "id", count="exact"
        ).eq("status", "dead_letter").execute()
        pending_dl = dl_resp.count or 0
        criteria["no_dead_letters"] = {
            "pass": pending_dl == 0,
            "pending": pending_dl,
            "required": "0 pending dead-letters",
        }
    except Exception as e:
        criteria["no_dead_letters"] = {"pass": False, "error": str(e)}

    # Overall
    all_pass = all(c.get("pass", False) for c in criteria.values())

    return {
        "ready_for_graduation": all_pass,
        "criteria": criteria,
        "checked_at": now.isoformat(),
    }
