import time
from typing import Optional
from datetime import datetime, timezone
from ..db import get_supabase
from . import binance_client
import logging

logger = logging.getLogger(__name__)


async def execute_proposal(proposal_id: str) -> dict:
    supabase = get_supabase()

    # 1. Fetch proposal
    resp = supabase.table("trade_proposals").select("*").eq("id", proposal_id).single().execute()
    if not resp.data:
        return {"success": False, "error": "Proposal not found"}

    proposal = resp.data
    if proposal["status"] != "approved":
        return {"success": False, "error": f"Proposal status is '{proposal['status']}', must be 'approved'"}

    symbol = proposal["symbol"]
    side = "BUY" if proposal["type"] == "buy" else "SELL"
    order_type = proposal.get("order_type", "MARKET")
    quantity = float(proposal["quantity"])
    price = float(proposal["price"]) if proposal.get("price") else None

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

        executed_qty = float(order.get("executedQty", quantity))
        commission = sum(float(f.get("commission", 0)) for f in fills)
        commission_asset = fills[0].get("commissionAsset", "BNB") if fills else "BNB"

        now = datetime.now(timezone.utc).isoformat()

        # 4. Update proposal to executed
        supabase.table("trade_proposals").update({
            "status": "executed",
            "binance_order_id": order_id,
            "executed_price": executed_price,
            "executed_quantity": executed_qty,
            "commission": commission,
            "commission_asset": commission_asset,
            "executed_at": now,
            "updated_at": now,
        }).eq("id", proposal_id).execute()

        # 5. Update positions
        proposal_id_str = str(proposal_id)
        if side == "BUY":
            await _open_position(supabase, symbol, executed_price, executed_qty, order_id, proposal_id_str, commission, commission_asset, proposal.get("strategy_id"))
        else:
            await _close_position(supabase, symbol, executed_price, executed_qty, order_id, proposal_id_str, commission, commission_asset)

        # 6. Log risk event
        await _log_risk_event(supabase, "order_executed", "info",
            f"Order executed successfully: {side} {executed_qty} {symbol} @ {executed_price}",
            {"order_id": order_id, "price": executed_price, "qty": executed_qty},
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
        supabase.table("trade_proposals").update({
            "status": "error",
            "error_message": str(e),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", proposal_id).execute()
        await _log_risk_event(supabase, "execution_error", "critical",
            f"Execution failed: {e}", {"proposal_id": proposal_id}, proposal_id=proposal_id)
        return {"success": False, "error": str(e)}


async def _open_position(supabase, symbol, price, qty, order_id, proposal_id, commission, commission_asset, strategy_id):
    now = datetime.now(timezone.utc).isoformat()
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
        "status": "open",
        "strategy_id": strategy_id,
        "opened_at": now,
        "updated_at": now,
    }).execute()

    await _log_risk_event(supabase, "position_opened", "info",
        f"Opened LONG {qty} {symbol} @ {price}", {"price": price, "qty": qty}, proposal_id=proposal_id)


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
