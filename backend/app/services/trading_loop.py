import asyncio
import logging
from datetime import datetime, timezone
from .executor import execute_all_approved
from .portfolio import get_portfolio_state
from ..db import get_supabase
from ..config import settings

logger = logging.getLogger(__name__)

_running = False


async def run_loop(interval_seconds: int = 60):
    """24/7 trading loop: quant tick -> execute approved -> update portfolio -> sleep."""
    global _running
    _running = True
    logger.info(f"Trading loop started (interval: {interval_seconds}s)")

    while _running:
        try:
            # Run quant engine tick (data collection + analysis)
            if settings.quant_enabled:
                try:
                    from .quant_orchestrator import run_quant_tick
                    await run_quant_tick()
                except Exception as e:
                    logger.error(f"Quant tick error: {e}")

            supabase = get_supabase()

            # Kill switch: skip execution if trading is disabled
            if not settings.trading_enabled:
                logger.debug("Trading disabled (kill switch) — skipping execution")
            else:
                # Execute any approved proposals
                result = await execute_all_approved(supabase)
                if result["executed"] > 0:
                    logger.info(f"Loop executed {result['executed']} proposals")

            # Update portfolio state (refreshes position prices)
            await get_portfolio_state()

            # Reconciliation: compare DB vs exchange
            try:
                from .reconciliation import run_reconciliation
                await run_reconciliation()
            except Exception as e:
                logger.error(f"Reconciliation error: {e}")

            # Daily report: send once per day around midnight UTC
            try:
                now = datetime.now(timezone.utc)
                if now.hour == 0 and now.minute < 2:
                    from .daily_report import already_sent_today, send_daily_report
                    if not already_sent_today():
                        await send_daily_report()
                        logger.info("Daily report sent")
            except Exception as e:
                logger.error(f"Daily report error: {e}")

        except Exception as e:
            logger.error(f"Trading loop error: {e}")

        await asyncio.sleep(interval_seconds)


def stop_loop():
    global _running
    _running = False
    logger.info("Trading loop stopped")
