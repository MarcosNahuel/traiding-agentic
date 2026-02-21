import asyncio
import logging
from datetime import datetime, timezone
from .executor import execute_all_approved
from .portfolio import get_portfolio_state
from ..db import get_supabase
from ..config import settings
from . import binance_client

logger = logging.getLogger(__name__)

_running = False

# Latency settings
MAIN_INTERVAL = 60    # Full tick: indicators + signals + execution
FAST_INTERVAL = 5     # Fast tick: only SL/TP price check (cheap: 5 API calls)


async def run_loop(interval_seconds: int = MAIN_INTERVAL):
    """Start both loops concurrently: fast SL/TP (5s) + full analysis (60s)."""
    global _running
    _running = True
    logger.info(f"Trading loop started — fast={FAST_INTERVAL}s / main={interval_seconds}s")

    await asyncio.gather(
        _fast_loop(),
        _main_loop(interval_seconds),
    )


async def _fast_loop():
    """5-second loop: ONLY checks SL/TP prices. Cheap (1 request/symbol)."""
    while _running:
        try:
            if settings.trading_enabled:
                await _check_stop_losses()
        except Exception as e:
            logger.error(f"Fast loop error: {e}")
        await asyncio.sleep(FAST_INTERVAL)


async def _main_loop(interval_seconds: int):
    """60-second loop: quant tick + signals + execution + portfolio + reconciliation."""
    while _running:
        try:
            # 1. Quant engine tick (klines + indicators)
            if settings.quant_enabled:
                try:
                    from .quant_orchestrator import run_quant_tick
                    await run_quant_tick()
                except Exception as e:
                    logger.error(f"Quant tick error: {e}")

            supabase = get_supabase()

            if not settings.trading_enabled:
                logger.debug("Trading disabled (kill switch)")
            else:
                # 2. Signal generation (quant -> proposals)
                try:
                    from .signal_generator import generate_signals
                    await generate_signals()
                except Exception as e:
                    logger.error(f"Signal generation error: {e}")

                # 3. Execute approved proposals
                result = await execute_all_approved(supabase)
                if result["executed"] > 0:
                    logger.info(f"Executed {result['executed']} proposals")

            # 4. Update portfolio state
            await get_portfolio_state()

            # 5. Reconciliation
            try:
                from .reconciliation import run_reconciliation
                await run_reconciliation()
            except Exception as e:
                logger.error(f"Reconciliation error: {e}")

            # 6. Daily report
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
            logger.error(f"Main loop error: {e}")

        await asyncio.sleep(interval_seconds)


async def _check_stop_losses() -> None:
    """Check open positions for SL/TP triggers. Called every 5s."""
    supabase = get_supabase()
    resp = supabase.table("positions").select("*").eq("status", "open").execute()
    positions = [
        p for p in (resp.data or [])
        if p.get("stop_loss_price") or p.get("take_profit_price")
    ]
    if not positions:
        return

    for pos in positions:
        try:
            ticker = await binance_client.get_price(pos["symbol"])
            current_price = float(ticker["price"])

            sl = float(pos["stop_loss_price"]) if pos.get("stop_loss_price") else None
            tp = float(pos["take_profit_price"]) if pos.get("take_profit_price") else None

            triggered = None
            if sl and current_price <= sl:
                triggered = ("stop_loss", sl)
            elif tp and current_price >= tp:
                triggered = ("take_profit", tp)

            if triggered:
                trigger_type, trigger_price = triggered
                logger.warning(
                    f"{trigger_type.upper()} [{pos['symbol']}] "
                    f"price={current_price:,.2f} level={trigger_price:,.2f}"
                )
                await _execute_sl_tp(supabase, pos, current_price, trigger_type)

        except Exception as e:
            logger.error(f"SL/TP check [{pos.get('symbol', '?')}]: {e}")


async def _execute_sl_tp(supabase, position: dict, current_price: float, trigger_type: str) -> None:
    """Auto-approve and execute a market sell for SL/TP."""
    symbol = position["symbol"]
    quantity = float(position["current_quantity"])
    now = datetime.now(timezone.utc).isoformat()

    insert = {
        "type": "sell",
        "symbol": symbol,
        "quantity": quantity,
        "price": current_price,
        "order_type": "MARKET",
        "notional": quantity * current_price,
        "status": "approved",
        "reasoning": f"[{trigger_type.upper()}] Auto-triggered @ ${current_price:,.2f}",
        "risk_score": 0,
        "risk_checks": [],
        "auto_approved": True,
        "retry_count": 0,
        "created_at": now,
        "updated_at": now,
        "approved_at": now,
    }
    resp = supabase.table("trade_proposals").insert(insert).execute()
    if not resp.data:
        logger.error(f"Failed to create {trigger_type} proposal for {symbol}")
        return

    proposal_id = resp.data[0]["id"]

    supabase.table("risk_events").insert({
        "event_type": trigger_type,
        "severity": "warning" if trigger_type == "stop_loss" else "info",
        "message": f"{trigger_type.upper()} SELL {quantity} {symbol} @ ${current_price:,.2f}",
        "details": {"position_id": position["id"], "trigger_price": current_price},
        "position_id": position["id"],
        "proposal_id": proposal_id,
    }).execute()

    try:
        from .telegram_notifier import send_telegram
        pnl = (current_price - float(position["entry_price"])) * quantity
        pnl_pct = (pnl / (float(position["entry_price"]) * quantity)) * 100
        emoji = "🛑" if trigger_type == "stop_loss" else "🎯"
        await send_telegram(
            f"{emoji} <b>{trigger_type.upper()}: {symbol}</b>\n"
            f"Entry: ${float(position['entry_price']):,.2f} → Exit: ${current_price:,.2f}\n"
            f"Cantidad: {quantity} | PnL: ${pnl:.2f} ({pnl_pct:+.1f}%)\n"
            f"\n<a href='https://traiding-agentic.vercel.app/trades'>Ver trades</a>"
        )
    except Exception:
        pass

    from .executor import execute_proposal
    result = await execute_proposal(proposal_id)
    logger.info(f"{trigger_type} execution: {result}")


def stop_loop():
    global _running
    _running = False
    logger.info("Trading loop stopped")
