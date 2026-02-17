from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from ..models import CreateProposalRequest, ApproveProposalRequest, ValidationResult
from ..services.risk_manager import validate_proposal
from ..services import binance_client
from ..db import get_supabase
import logging

router = APIRouter(prefix="/proposals")
logger = logging.getLogger(__name__)


@router.post("")
async def create_proposal(req: CreateProposalRequest):
    supabase = get_supabase()

    # Get current price
    try:
        ticker = await binance_client.get_price(req.symbol)
        current_price = float(ticker["price"])
    except Exception as e:
        raise HTTPException(400, f"Could not fetch price for {req.symbol}: {e}")

    price = req.price if req.price else current_price
    notional = req.quantity * price
    now = datetime.now(timezone.utc).isoformat()

    # Insert draft proposal
    insert_data = {
        "type": req.type,
        "symbol": req.symbol,
        "quantity": req.quantity,
        "price": price,
        "order_type": req.order_type,
        "notional": notional,
        "status": "draft",
        "strategy_id": req.strategy_id,
        "reasoning": req.reasoning,
        "risk_score": 0,
        "risk_checks": [],
        "auto_approved": False,
        "retry_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    resp = supabase.table("trade_proposals").insert(insert_data).execute()
    if not resp.data:
        raise HTTPException(500, "Failed to create proposal")

    proposal = resp.data[0]
    proposal_id = proposal["id"]

    # Run risk validation
    validation: ValidationResult = await validate_proposal(
        trade_type=req.type,
        symbol=req.symbol,
        quantity=req.quantity,
        notional=notional,
        current_price=current_price,
    )

    # Determine final status
    if not validation.approved:
        new_status = "rejected"
        rejected_at = now
    elif validation.auto_approved:
        new_status = "approved"
        rejected_at = None
    else:
        new_status = "validated"
        rejected_at = None

    update_data = {
        "status": new_status,
        "risk_score": validation.risk_score,
        "risk_checks": [c.model_dump() for c in validation.checks],
        "auto_approved": validation.auto_approved,
        "validated_at": now,
        "updated_at": now,
    }
    if new_status == "rejected":
        update_data["rejected_at"] = now
    if new_status == "approved":
        update_data["approved_at"] = now

    supabase.table("trade_proposals").update(update_data).eq("id", proposal_id).execute()

    # Log risk event
    try:
        event_type = "proposal_rejected" if not validation.approved else "proposal_approved"
        severity = "warning" if not validation.approved else "info"
        msg = validation.rejection_reason if not validation.approved else f"Trade proposal validated: {req.type.upper()} {req.quantity} {req.symbol}"
        supabase.table("risk_events").insert({
            "event_type": event_type,
            "severity": severity,
            "message": msg,
            "details": {"notional": notional, "risk_score": validation.risk_score},
            "proposal_id": proposal_id,
        }).execute()
    except Exception as e:
        logger.warning(f"Failed to log risk event: {e}")

    # Auto-execute if auto-approved
    execution_result = None
    if new_status == "approved":
        from ..services.executor import execute_proposal
        execution_result = await execute_proposal(proposal_id)

    final = supabase.table("trade_proposals").select("*").eq("id", proposal_id).single().execute()

    return {
        "success": True,
        "proposalId": proposal_id,
        "status": final.data["status"] if final.data else new_status,
        "autoApproved": validation.auto_approved,
        "riskScore": validation.risk_score,
        "notional": f"${notional:.2f}",
        "estimatedPrice": f"${price:.2f}",
        "validation": {
            "approved": validation.approved,
            "checks": [c.model_dump() for c in validation.checks],
            "rejectionReason": validation.rejection_reason,
        },
        "proposal": final.data,
        "execution": execution_result,
    }


@router.get("")
async def list_proposals(status: str = None, symbol: str = None, type: str = None, limit: int = 50, offset: int = 0):
    supabase = get_supabase()
    query = supabase.table("trade_proposals").select("*", count="exact")
    if status:
        query = query.eq("status", status)
    if symbol:
        query = query.eq("symbol", symbol)
    if type:
        query = query.eq("type", type)
    resp = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    total = resp.count or 0
    proposals = resp.data or []

    # Stats
    all_resp = supabase.table("trade_proposals").select("status").execute()
    all_data = all_resp.data or []
    stats = {"pending": 0, "approved": 0, "rejected": 0, "executed": 0}
    for p in all_data:
        s = p["status"]
        if s in ("draft", "validated"):
            stats["pending"] += 1
        elif s in stats:
            stats[s] += 1

    return {"proposals": proposals, "total": total, "limit": limit, "offset": offset, "stats": stats}


@router.get("/{proposal_id}")
async def get_proposal(proposal_id: str):
    supabase = get_supabase()
    resp = supabase.table("trade_proposals").select("*").eq("id", proposal_id).single().execute()
    if not resp.data:
        raise HTTPException(404, "Proposal not found")
    return {"proposal": resp.data}


@router.patch("/{proposal_id}")
async def update_proposal(proposal_id: str, req: ApproveProposalRequest):
    supabase = get_supabase()
    resp = supabase.table("trade_proposals").select("*").eq("id", proposal_id).single().execute()
    if not resp.data:
        raise HTTPException(404, "Proposal not found")

    proposal = resp.data
    if proposal["status"] != "validated":
        raise HTTPException(400, f"Can only approve/reject proposals in 'validated' status (current: {proposal['status']})")

    now = datetime.now(timezone.utc).isoformat()
    if req.action == "approve":
        supabase.table("trade_proposals").update({
            "status": "approved", "approved_at": now, "updated_at": now
        }).eq("id", proposal_id).execute()
        supabase.table("risk_events").insert({
            "event_type": "proposal_approved", "severity": "info",
            "message": f"Trade proposal approved by user", "details": {"notes": req.notes},
            "proposal_id": proposal_id,
        }).execute()
        return {"success": True, "proposalId": proposal_id, "status": "approved"}
    elif req.action == "reject":
        supabase.table("trade_proposals").update({
            "status": "rejected", "rejected_at": now, "updated_at": now
        }).eq("id", proposal_id).execute()
        supabase.table("risk_events").insert({
            "event_type": "proposal_rejected", "severity": "warning",
            "message": f"Trade proposal rejected by user", "details": {"notes": req.notes},
            "proposal_id": proposal_id,
        }).execute()
        return {"success": True, "proposalId": proposal_id, "status": "rejected"}
    else:
        raise HTTPException(400, f"Unknown action: {req.action}")
