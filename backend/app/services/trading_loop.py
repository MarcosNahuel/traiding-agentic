import asyncio
import logging
from datetime import datetime, timezone
from .executor import execute_all_approved
from .portfolio import get_portfolio_state
from ..db import get_supabase

logger = logging.getLogger(__name__)

_running = False


async def run_loop(interval_seconds: int = 60):
    """24/7 trading loop: auto-executes approved proposals + updates positions."""
    global _running
    _running = True
    logger.info(f"Trading loop started (interval: {interval_seconds}s)")

    while _running:
        try:
            supabase = get_supabase()

            # Execute any approved proposals
            result = await execute_all_approved(supabase)
            if result["executed"] > 0:
                logger.info(f"Loop executed {result['executed']} proposals")

            # Update portfolio state (refreshes position prices)
            await get_portfolio_state()

        except Exception as e:
            logger.error(f"Trading loop error: {e}")

        await asyncio.sleep(interval_seconds)


def stop_loop():
    global _running
    _running = False
    logger.info("Trading loop stopped")
