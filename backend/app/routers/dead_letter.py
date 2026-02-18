from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from ..db import get_supabase
from ..services.executor import execute_proposal
import logging

router = APIRouter(prefix="/dead-letters", tags=["dead-letters"])
logger = logging.getLogger(__name__)


@router.get("")
async def list_dead_letters():
    """List all proposals in dead_letter status."""
    supabase = get_supabase()
    resp = supabase.table("trade_proposals").select("*").eq(
        "status", "dead_letter"
    ).order("updated_at", desc=True).execute()
    return {"dead_letters": resp.data or [], "count": len(resp.data or [])}


@router.post("/{proposal_id}/retry")
async def retry_dead_letter(proposal_id: str):
    """Reset a dead-letter proposal to approved and re-execute."""
    supabase = get_supabase()

    resp = supabase.table("trade_proposals").select("*").eq(
        "id", proposal_id
    ).single().execute()
    if not resp.data:
        raise HTTPException(404, "Proposal not found")
    if resp.data["status"] != "dead_letter":
        raise HTTPException(400, f"Proposal status is '{resp.data['status']}', must be 'dead_letter'")

    # Reset to approved
    supabase.table("trade_proposals").update({
        "status": "approved",
        "retry_count": 0,
        "error_message": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", proposal_id).execute()

    # Re-execute
    result = await execute_proposal(proposal_id)
    return {"success": True, "execution_result": result}


@router.post("/{proposal_id}/cancel")
async def cancel_dead_letter(proposal_id: str):
    """Cancel a dead-letter proposal."""
    supabase = get_supabase()

    resp = supabase.table("trade_proposals").select("id, status").eq(
        "id", proposal_id
    ).single().execute()
    if not resp.data:
        raise HTTPException(404, "Proposal not found")
    if resp.data["status"] != "dead_letter":
        raise HTTPException(400, f"Proposal status is '{resp.data['status']}', must be 'dead_letter'")

    supabase.table("trade_proposals").update({
        "status": "cancelled",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", proposal_id).execute()

    return {"success": True, "status": "cancelled"}
