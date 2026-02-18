from fastapi import APIRouter, Query
from ..services.reconciliation import (
    run_reconciliation,
    get_latest_reconciliation,
    get_reconciliation_history,
)
from ..services.daily_report import send_daily_report
import logging

router = APIRouter(tags=["reconciliation"])
logger = logging.getLogger(__name__)


@router.post("/reconciliation/run")
async def trigger_reconciliation():
    """Trigger a manual reconciliation run."""
    result = await run_reconciliation()
    return result


@router.get("/reconciliation/latest")
async def latest_reconciliation():
    """Get the most recent reconciliation result."""
    result = await get_latest_reconciliation()
    if not result:
        return {"message": "No reconciliation runs yet"}
    return result


@router.get("/reconciliation/history")
async def reconciliation_history(limit: int = Query(default=20, le=100)):
    """Get reconciliation run history."""
    results = await get_reconciliation_history(limit=limit)
    return {"runs": results, "count": len(results)}


@router.post("/reports/daily")
async def trigger_daily_report():
    """Trigger a manual daily report via Telegram."""
    result = await send_daily_report()
    return result
