"""Scheduler for daily LLM analyst runs.

Pre-market: 23:00 UTC (1h before "new day")
Post-market: 00:05 UTC (after daily report)
"""

import logging
from datetime import datetime, timezone

from .graphs import build_pre_market_graph, build_post_market_graph

logger = logging.getLogger(__name__)

_pre_market_ran_today: str = ""
_post_market_ran_today: str = ""


def should_run_pre_market(now: datetime) -> bool:
    """True if 23:00-23:02 UTC and not yet run today."""
    global _pre_market_ran_today
    today = now.strftime("%Y-%m-%d")
    return now.hour == 23 and now.minute < 2 and _pre_market_ran_today != today


def should_run_post_market(now: datetime) -> bool:
    """True if 00:05-00:10 UTC and not yet run today."""
    global _post_market_ran_today
    today = now.strftime("%Y-%m-%d")
    return now.hour == 0 and 5 <= now.minute < 10 and _post_market_ran_today != today


async def run_pre_market_analysis() -> dict:
    """Execute the pre-market LangGraph analysis."""
    global _pre_market_ran_today
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info("Starting pre-market LLM analysis...")
    try:
        graph = build_pre_market_graph()
        result = await graph.ainvoke({
            "messages": [],
            "market_data": "",
            "proposed_config": None,
            "validated_config": None,
            "warnings": [],
            "brief": None,
            "error": None,
        })
        _pre_market_ran_today = today
        logger.info("Pre-market analysis complete: %s",
                     "success" if result.get("brief") else result.get("error", "unknown"))
        return result
    except Exception as e:
        logger.error("Pre-market analysis failed: %s", e)
        _pre_market_ran_today = today  # Don't retry on failure
        return {"error": str(e)}


async def run_post_market_audit() -> dict:
    """Execute the post-market LangGraph audit."""
    global _post_market_ran_today
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info("Starting post-market LLM audit...")
    try:
        graph = build_post_market_graph()
        result = await graph.ainvoke({
            "messages": [],
            "performance_data": "",
            "audit": None,
            "error": None,
        })
        _post_market_ran_today = today
        logger.info("Post-market audit complete: grade=%s",
                     result.get("audit", {}).get("overall_grade", "?"))
        return result
    except Exception as e:
        logger.error("Post-market audit failed: %s", e)
        _post_market_ran_today = today
        return {"error": str(e)}
