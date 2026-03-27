import asyncio
import logging
from datetime import datetime, timezone
from .executor import execute_all_approved, _compute_sl_tp
from .portfolio import get_portfolio_state
from ..db import get_supabase
from ..config import settings
from . import binance_client
from ..utils.binance_utils import round_quantity

logger = logging.getLogger(__name__)

_running = False

# Latency settings
MAIN_INTERVAL = 60    # Full tick: indicators + signals + execution
FAST_INTERVAL = 2     # ERA 5 — Fast tick cada 2s para SL/TP más reactivo


async def run_loop(interval_seconds: int = MAIN_INTERVAL):
    """Start both loops concurrently: fast SL/TP (5s) + full analysis (60s)."""
    global _running
    _running = True
    logger.info(f"Trading loop started — fast={FAST_INTERVAL}s / main={interval_seconds}s")

    # Emergency SL check: close positions that breached SL while backend was down
    if settings.trading_enabled:
        await _emergency_sl_check()

    await asyncio.gather(
        _fast_loop(),
        _main_loop(interval_seconds),
    )


async def _emergency_sl_check() -> None:
    """On startup, immediately close any positions that already breached their SL.

    Prevents holding losers indefinitely when backend was down during a price drop.
    """
    supabase = get_supabase()
    resp = supabase.table("positions").select("*").eq("status", "open").execute()
    positions = resp.data or []
    if not positions:
        return

    closed = 0
    for pos in positions:
        sl = float(pos["stop_loss_price"]) if pos.get("stop_loss_price") else None
        if not sl:
            continue
        try:
            ticker = await binance_client.get_price(pos["symbol"])
            current_price = float(ticker["price"])
            if current_price <= sl:
                logger.warning(
                    "EMERGENCY SL [%s]: price=$%.2f already below SL=$%.2f — closing immediately",
                    pos["symbol"], current_price, sl,
                )
                await _execute_sl_tp(supabase, pos, current_price, "stop_loss")
                closed += 1
        except Exception as e:
            logger.error("Emergency SL check failed for %s: %s", pos.get("symbol", "?"), e)

    if closed:
        logger.warning("Emergency SL check closed %d positions on startup", closed)


async def _fast_loop():
    """2-second loop: checks SL/TP prices + trailing stop updates."""
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
    """Check open positions for SL/TP triggers. Repairs missing SL/TP. Called every 5s."""
    supabase = get_supabase()
    resp = supabase.table("positions").select("*").eq("status", "open").execute()
    positions = resp.data or []
    if not positions:
        return

    for pos in positions:
        # Reparar posiciones sin SL/TP
        if not pos.get("stop_loss_price") or not pos.get("take_profit_price"):
            await _repair_missing_sl_tp(supabase, pos)
            continue
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

            # Time stop: cerrar posiciones >48h (stale en 1h strategy)
            if not triggered and pos.get("opened_at"):
                from datetime import timedelta
                from dateutil.parser import parse as parse_dt
                try:
                    opened = parse_dt(pos["opened_at"])
                    age_hours = (datetime.now(timezone.utc) - opened).total_seconds() / 3600
                    if age_hours > 48:
                        triggered = ("time_stop", current_price)
                        logger.warning("TIME_STOP [%s] position age=%.0fh > 48h", pos["symbol"], age_hours)
                except Exception:
                    pass

            if triggered:
                trigger_type, trigger_price = triggered
                logger.warning(
                    f"{trigger_type.upper()} [{pos['symbol']}] "
                    f"price={current_price:,.2f} level={trigger_price:,.2f}"
                )
                await _execute_sl_tp(supabase, pos, current_price, trigger_type)
            else:
                # Trailing stop: si el precio subió, mover SL hacia arriba
                await _update_trailing_stop(supabase, pos, current_price, sl, tp)

        except Exception as e:
            logger.error(f"SL/TP check [{pos.get('symbol', '?')}]: {e}")


async def _execute_sl_tp(supabase, position: dict, current_price: float, trigger_type: str) -> None:
    """Auto-approve and execute a market sell for SL/TP.

    Uses atomic claim (UPDATE WHERE status=open → closing) to prevent
    the fast loop from creating duplicate sell proposals.
    """
    symbol = position["symbol"]
    pos_id = position["id"]

    # Atomic claim: prevent duplicate sells from the 2s fast loop
    # Step 1: attempt to claim by setting status to 'closing'
    supabase.table("positions").update({
        "status": "closing",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", pos_id).eq("status", "open").execute()

    # Step 2: verify the claim succeeded (SELECT is reliable across all supabase-py versions)
    verify = supabase.table("positions").select("status").eq("id", pos_id).execute()
    if not verify.data or verify.data[0].get("status") != "closing":
        logger.debug("Skipping %s for %s — already closing (anti-spam)", trigger_type, symbol)
        return

    logger.info("Claimed position %s for %s — proceeding with sell", pos_id[:8], trigger_type)

    quantity = round_quantity(symbol, float(position["current_quantity"]))
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


async def _update_trailing_stop(supabase, position: dict, current_price: float, sl: float, tp: float) -> None:
    """Trailing stop con Chandelier Exit (QS).

    Usa highest_high - k*ATR cuando ATR disponible (más adaptativo).
    Fallback: progress-based trailing si ATR no disponible.
    Solo activa cuando precio avanzó >65% hacia TP.
    """
    entry_price = float(position["entry_price"])
    if current_price <= entry_price or not sl or not tp:
        return

    # Distancia original: entry → TP
    original_tp_distance = tp - entry_price
    if original_tp_distance <= 0:
        return

    # Progreso: qué % del camino al TP hemos recorrido
    progress = (current_price - entry_price) / original_tp_distance

    # Solo activar trailing si avanzamos >65% hacia el TP
    if progress < 0.65:
        return

    # QS: Chandelier Exit — usa current_price como proxy de highest_high
    # (en polling cada 2s, current_price ≈ highest recent high)
    chandelier_sl = None
    try:
        from .technical_analysis import compute_indicators
        from ..config import settings
        ind = compute_indicators(position["symbol"], settings.quant_primary_interval)
        if ind and ind.atr_14 and ind.atr_14 > 0:
            chandelier_sl = compute_chandelier_sl(current_price, ind.atr_14, 2.0)
    except Exception:
        pass

    # Fallback: progress-based trailing
    trail_pct = max(0, progress - 0.30)
    progress_sl = round(entry_price + trail_pct * original_tp_distance, 2)

    # Elegir el mejor SL: el más alto (más protector) entre Chandelier y progress
    if chandelier_sl and chandelier_sl > entry_price:
        new_sl = max(chandelier_sl, progress_sl)
    else:
        new_sl = progress_sl

    # Solo subir el SL, nunca bajarlo
    if new_sl <= sl:
        return

    supabase.table("positions").update({
        "stop_loss_price": new_sl,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", position["id"]).execute()

    logger.info(
        "TRAILING SL [%s] moved: $%.2f → $%.2f (price=$%.2f, progress=%.0f%%)",
        position["symbol"], sl, new_sl, current_price, progress * 100
    )


async def _repair_missing_sl_tp(supabase, position: dict) -> None:
    """Computa SL/TP via ATR para posiciones que no los tienen."""
    symbol = position["symbol"]
    entry_price = float(position["entry_price"])

    sl_price, tp_price = _compute_sl_tp(symbol, entry_price)

    supabase.table("positions").update({
        "stop_loss_price": sl_price,
        "take_profit_price": tp_price,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", position["id"]).execute()

    logger.warning("Repaired SL/TP for %s [%s]: SL=$%.2f TP=$%.2f",
                    symbol, position["id"], sl_price, tp_price)

    try:
        supabase.table("risk_events").insert({
            "event_type": "sl_tp_repaired",
            "severity": "warning",
            "message": f"Repaired missing SL/TP for {symbol}: SL=${sl_price:.2f} TP=${tp_price:.2f}",
            "details": {"entry_price": entry_price, "sl_price": sl_price, "tp_price": tp_price},
            "position_id": position["id"],
        }).execute()
    except Exception:
        pass


def compute_chandelier_sl(highest_high: float, atr: float, multiplier: float = 2.0) -> float | None:
    """Chandelier Exit: SL = highest_high - k * ATR. Más adaptativo que trailing fijo."""
    if not highest_high or highest_high <= 0:
        return None
    if not atr or atr <= 0:
        return None
    return round(highest_high - multiplier * atr, 2)


def stop_loop():
    global _running
    _running = False
    logger.info("Trading loop stopped")
