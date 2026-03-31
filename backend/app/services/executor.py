import time
from typing import Optional
from datetime import datetime, timezone
from ..db import get_supabase
from ..config import settings
from . import binance_client
from .technical_analysis import compute_indicators
import logging

logger = logging.getLogger(__name__)


async def _convert_commission_to_usdt(commission: float, commission_asset: str) -> float:
    """Convert commission to USDT equivalent. If already USDT, return as-is."""
    if commission_asset in ("USDT", "FDUSD", "USDC") or commission == 0:
        return commission
    try:
        ticker = await binance_client.get_price(f"{commission_asset}USDT")
        rate = float(ticker.get("price", 0))
        if rate > 0:
            return commission * rate
    except Exception as e:
        logger.warning("Could not convert %s commission to USDT: %s", commission_asset, e)
    return commission  # fallback: return raw


async def execute_proposal(proposal_id: str) -> dict:
    # Kill switch check
    if not settings.trading_enabled:
        return {"success": False, "error": "Trading is disabled (kill switch)"}

    supabase = get_supabase()
    now = datetime.now(timezone.utc).isoformat()

    # 1. Atomic claim: UPDATE WHERE status="approved" → "executing"
    # Solo un caller puede reclamar el proposal (compare-and-swap via PostgREST)
    claimed = supabase.table("trade_proposals").update({
        "status": "executing",
        "updated_at": now,
    }).eq("id", proposal_id).eq("status", "approved").execute()

    if not claimed.data:
        # Verificar si ya está siendo ejecutado o no existe
        check = supabase.table("trade_proposals").select("status").eq("id", proposal_id).execute()
        if check.data:
            current = check.data[0]["status"]
            return {"success": False, "error": f"Proposal not claimable: status='{current}' (already executing or executed)"}
        return {"success": False, "error": "Proposal not found"}

    proposal = claimed.data[0]
    symbol = proposal["symbol"]
    side = "BUY" if proposal["type"] == "buy" else "SELL"
    order_type = proposal.get("order_type", "MARKET")
    quantity = float(proposal["quantity"])
    price = float(proposal["price"]) if proposal.get("price") else None

    # ── EXECUTION-TIME RISK GUARD ──
    # Re-validate limits right before placing the order.
    # Prevents duplicates when multiple proposals were approved before any executed.
    if side == "BUY":
        sym_resp = supabase.table("positions").select("id").eq("symbol", symbol).eq("status", "open").execute()
        sym_count = len(sym_resp.data) if sym_resp.data else 0
        if sym_count >= settings.risk_max_positions_per_symbol:
            supabase.table("trade_proposals").update({
                "status": "rejected",
                "error_message": f"Execution guard: {sym_count} open positions for {symbol} (max {settings.risk_max_positions_per_symbol})",
                "updated_at": now,
            }).eq("id", proposal_id).execute()
            logger.warning("Execution blocked: %d open positions for %s (max %d)", sym_count, symbol, settings.risk_max_positions_per_symbol)
            return {"success": False, "error": f"Per-symbol limit: {sym_count}/{settings.risk_max_positions_per_symbol}"}

        open_resp = supabase.table("positions").select("id").eq("status", "open").execute()
        open_count = len(open_resp.data) if open_resp.data else 0
        if open_count >= settings.risk_max_open_positions:
            supabase.table("trade_proposals").update({
                "status": "rejected",
                "error_message": f"Execution guard: {open_count} total open (max {settings.risk_max_open_positions})",
                "updated_at": now,
            }).eq("id", proposal_id).execute()
            logger.warning("Execution blocked: %d total open positions (max %d)", open_count, settings.risk_max_open_positions)
            return {"success": False, "error": f"Max positions: {open_count}/{settings.risk_max_open_positions}"}

    try:
        # 2. Place order
        order = await binance_client.place_order(symbol, side, order_type, quantity, price)
        logger.info(f"Order placed: {order}")

        if "code" in order and order["code"] < 0:
            raise Exception(f"Binance error {order['code']}: {order.get('msg', 'Unknown')}")

        order_id = order.get("orderId")

        # 3. Extract fill price
        fills = order.get("fills", [])
        executed_price = 0.0
        if fills:
            executed_price = float(fills[0].get("price", 0))
        if executed_price == 0.0:
            raw_price = float(order.get("price", 0))
            if raw_price > 0:
                executed_price = raw_price
            else:
                # Fetch current price as fallback
                ticker = await binance_client.get_price(symbol)
                executed_price = float(ticker.get("price", 0))

        # Handle order status (partial fills, canceled, etc.)
        order_status = order.get("status", "FILLED")
        executed_qty = float(order.get("executedQty", 0))

        if order_status in ("CANCELED", "EXPIRED", "REJECTED") or executed_qty == 0:
            supabase.table("trade_proposals").update({
                "status": "error",
                "error_message": f"Order {order_status}: executedQty=0",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", proposal_id).execute()
            return {"success": False, "error": f"Order {order_status}"}

        commission_raw = sum(float(f.get("commission", 0)) for f in fills)
        commission_asset = fills[0].get("commissionAsset", "BNB") if fills else "BNB"
        commission = await _convert_commission_to_usdt(commission_raw, commission_asset)

        now = datetime.now(timezone.utc).isoformat()

        # 4. Update proposal
        proposal_status = "executed" if order_status == "FILLED" else "partially_filled"
        supabase.table("trade_proposals").update({
            "status": proposal_status,
            "binance_order_id": order_id,
            "executed_price": executed_price,
            "executed_quantity": executed_qty,
            "commission": commission,
            "commission_asset": commission_asset,
            "executed_at": now,
            "updated_at": now,
        }).eq("id", proposal_id).execute()

        # 5. Update positions (use actual executed_qty, not requested)
        proposal_id_str = str(proposal_id)
        if side == "BUY":
            await _open_position(supabase, symbol, executed_price, executed_qty, order_id, proposal_id_str, commission, commission_asset, proposal.get("strategy_id"))
        else:
            await _close_position(supabase, symbol, executed_price, executed_qty, order_id, proposal_id_str, commission, commission_asset)

        # 6. Log risk event
        fill_info = f"({order_status})" if order_status != "FILLED" else ""
        await _log_risk_event(supabase, "order_executed", "info",
            f"Order executed{fill_info}: {side} {executed_qty} {symbol} @ {executed_price}",
            {"order_id": order_id, "price": executed_price, "qty": executed_qty, "order_status": order_status},
            proposal_id=proposal_id_str)

        return {
            "success": True,
            "order_id": order_id,
            "executed_price": executed_price,
            "executed_quantity": executed_qty,
            "commission": commission,
            "commission_asset": commission_asset,
        }

    except Exception as e:
        logger.error(f"Execution failed for {proposal_id}: {e}")

        # 4xx client errors are permanent (bad params, insufficient balance, etc.)
        # Never retry them — they won't succeed without fixing the underlying issue.
        error_str = str(e)
        is_permanent = any(code in error_str for code in ("400 Bad Request", "400 Client Error", "422"))

        if is_permanent:
            new_status = "error"
            current_retry = proposal.get("retry_count") or 0  # Don't increment
            logger.error(f"Permanent client error for {proposal_id} ({symbol}), marking as error (no retry): {e}")
        else:
            current_retry = (proposal.get("retry_count") or 0) + 1
            is_dead_letter = current_retry >= 3
            new_status = "dead_letter" if is_dead_letter else "error"
        supabase.table("trade_proposals").update({
            "status": new_status,
            "error_message": str(e),
            "retry_count": current_retry,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", proposal_id).execute()

        severity = "critical"
        event_type = "execution_error"
        if not is_permanent and is_dead_letter:
            event_type = "dead_letter"
            # Send Telegram alert for dead letter
            try:
                from .telegram_notifier import escape_html, send_telegram
                sent = await send_telegram(
                    f"<b>DEAD LETTER</b>\n"
                    f"Proposal <code>{escape_html(proposal_id)}</code> moved to dead_letter after {current_retry} failures.\n"
                    f"Symbol: {escape_html(proposal.get('symbol', '?'))}\n"
                    f"Error: {escape_html(str(e))}"
                )
                if not sent:
                    logger.warning("Failed to send Telegram dead-letter alert for %s", proposal_id)
            except Exception:
                pass

        await _log_risk_event(supabase, event_type, severity,
            f"Execution failed ({new_status}): {e}", {"proposal_id": proposal_id, "retry_count": current_retry}, proposal_id=proposal_id)
        return {"success": False, "error": str(e), "status": new_status}


_MAX_ATR_PRICE_RATIO = 0.25  # ATR no puede ser > 25% del precio (filtro de sanidad)


def _compute_sl_tp(symbol: str, price: float) -> tuple[float, float]:
    """Calcula SL/TP basado en ATR. Fallback a porcentaje fijo si ATR es inválido."""

    def _fallback() -> tuple[float, float]:
        sl = round(price * (1 - settings.sl_fallback_pct), 2)
        tp = round(price * (1 + settings.tp_fallback_pct), 2)
        logger.info("SL/TP fallback: SL=$%.2f TP=$%.2f", sl, tp)
        return sl, tp

    if price <= 0:
        return _fallback()

    try:
        indicators = compute_indicators(symbol, settings.quant_primary_interval)
        atr = indicators.atr_14 if indicators else None

        if atr and atr > 0 and (atr / price) <= _MAX_ATR_PRICE_RATIO:
            sl_price = round(price - settings.sl_atr_multiplier * atr, 2)
            tp_price = round(price + settings.tp_atr_multiplier * atr, 2)

            # Sanity: SL debe ser < price y > 0, TP debe ser > price
            if 0 < sl_price < price < tp_price:
                logger.info("SL/TP via ATR=%.2f: SL=$%.2f TP=$%.2f", atr, sl_price, tp_price)
                return sl_price, tp_price
            else:
                logger.warning("ATR=%.2f generó SL/TP inválidos (SL=%.2f TP=%.2f) para price=%.2f — usando fallback",
                               atr, sl_price, tp_price, price)
        elif atr and (atr / price) > _MAX_ATR_PRICE_RATIO:
            logger.warning("ATR=%.2f es > %.0f%% del precio %.2f (aberrante) — usando fallback",
                           atr, _MAX_ATR_PRICE_RATIO * 100, price)
    except Exception as e:
        logger.warning("ATR computation failed for %s: %s", symbol, e)

    return _fallback()


async def _open_position(supabase, symbol, price, qty, order_id, proposal_id, commission, commission_asset, strategy_id):
    now = datetime.now(timezone.utc).isoformat()

    # Calcula SL/TP basado en ATR (1:2 risk:reward)
    sl_price, tp_price = _compute_sl_tp(symbol, price)

    try:
        # Get current price for unrealized PnL
        ticker = await binance_client.get_price(symbol)
        current_price = float(ticker.get("price", price))
    except Exception:
        current_price = price

    unrealized_pnl = (current_price - price) * qty - commission
    unrealized_pnl_pct = (unrealized_pnl / (price * qty)) * 100 if price * qty > 0 else 0

    supabase.table("positions").insert({
        "symbol": symbol,
        "side": "long",
        "entry_price": price,
        "entry_quantity": qty,
        "entry_notional": price * qty,
        "entry_order_id": order_id,
        "entry_proposal_id": proposal_id,
        "current_price": current_price,
        "current_quantity": qty,
        "unrealized_pnl": unrealized_pnl,
        "unrealized_pnl_percent": unrealized_pnl_pct,
        "total_commission": commission,
        "commission_asset": commission_asset,
        "stop_loss_price": sl_price,
        "take_profit_price": tp_price,
        "status": "open",
        "strategy_id": strategy_id,
        "opened_at": now,
        "updated_at": now,
    }).execute()

    logger.info(f"Position opened with SL=${sl_price:.2f} TP=${tp_price:.2f}")
    await _log_risk_event(supabase, "position_opened", "info",
        f"Opened LONG {qty} {symbol} @ {price}", {"price": price, "qty": qty, "sl_price": sl_price, "tp_price": tp_price}, proposal_id=proposal_id)


async def _close_position(supabase, symbol, exit_price, exit_qty, order_id, proposal_id, commission, commission_asset):
    now = datetime.now(timezone.utc).isoformat()

    # Find open position for this symbol
    resp = supabase.table("positions").select("*").eq("symbol", symbol).eq("status", "open").order("opened_at").execute()
    if not resp.data:
        logger.warning(f"No open position found for {symbol} to close")
        return

    position = resp.data[0]
    entry_price = float(position["entry_price"])
    entry_qty = float(position["entry_quantity"])
    total_commission = float(position.get("total_commission", 0)) + commission

    if exit_qty > entry_qty:
        logger.warning(f"Exit qty {exit_qty} > entry qty {entry_qty} for {symbol}, clamping to entry qty")
        exit_qty = entry_qty

    realized_pnl = (exit_price - entry_price) * exit_qty - total_commission
    realized_pnl_pct = (realized_pnl / (entry_price * exit_qty)) * 100 if entry_price * exit_qty > 0 else 0

    remaining_qty = entry_qty - exit_qty
    new_status = "closed" if remaining_qty <= 0.0001 else "partially_closed"

    supabase.table("positions").update({
        "exit_price": exit_price,
        "exit_quantity": exit_qty,
        "exit_notional": exit_price * exit_qty,
        "exit_order_id": order_id,
        "exit_proposal_id": proposal_id,
        "realized_pnl": realized_pnl,
        "realized_pnl_percent": realized_pnl_pct,
        "current_quantity": max(remaining_qty, 0),
        "total_commission": total_commission,
        "status": new_status,
        "closed_at": now if new_status == "closed" else None,
        "updated_at": now,
    }).eq("id", position["id"]).execute()

    await _log_risk_event(supabase, "position_closed", "info",
        f"Closed {exit_qty} {symbol} @ {exit_price} | PnL: ${realized_pnl:.4f}",
        {"realized_pnl": realized_pnl, "exit_price": exit_price}, proposal_id=proposal_id)


async def execute_all_approved(supabase=None) -> dict:
    if supabase is None:
        supabase = get_supabase()
    resp = supabase.table("trade_proposals").select("id").eq("status", "approved").order("created_at").execute()
    proposals = resp.data or []
    executed = 0
    failed = 0
    results = []
    for p in proposals:
        result = await execute_proposal(p["id"])
        if result["success"]:
            executed += 1
        else:
            failed += 1
        results.append(result)
        import asyncio
        await asyncio.sleep(0.1)
    return {"executed": executed, "failed": failed, "total": len(proposals), "results": results}


async def _log_risk_event(supabase, event_type: str, severity: str, message: str, details: dict = None, position_id: str = None, proposal_id: str = None):
    try:
        supabase.table("risk_events").insert({
            "event_type": event_type,
            "severity": severity,
            "message": message,
            "details": details or {},
            "position_id": position_id,
            "proposal_id": proposal_id,
        }).execute()
    except Exception as e:
        logger.warning(f"Failed to log risk event: {e}")
