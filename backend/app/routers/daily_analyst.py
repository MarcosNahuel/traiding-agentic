"""API endpoints for the Daily LLM Analyst."""

import asyncio
from fastapi import APIRouter

router = APIRouter(prefix="/analyst", tags=["analyst"])


@router.get("/config")
async def get_active_config():
    """Get the current active LLM trading config."""
    from ..services.daily_analyst.config_bridge import load_active_config
    config = load_active_config()
    if config:
        return {"status": "active", "config": config.model_dump()}
    return {"status": "none", "config": None, "message": "Using default settings"}


@router.post("/run-premarket")
async def trigger_premarket():
    """Manually trigger pre-market analysis."""
    from ..services.daily_analyst.scheduler import run_pre_market_analysis
    asyncio.create_task(run_pre_market_analysis())
    return {"status": "launched", "message": "Pre-market analysis running in background"}


@router.post("/run-audit")
async def trigger_audit():
    """Manually trigger post-market audit."""
    from ..services.daily_analyst.scheduler import run_post_market_audit
    asyncio.create_task(run_post_market_audit())
    return {"status": "launched", "message": "Post-market audit running in background"}
