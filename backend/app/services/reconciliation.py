"""Reconciliation service — compares DB state vs Binance exchange state.

Runs every tick (60s) to detect divergences:
- Orphan orders: on exchange but not tracked in DB
- Stale proposals: DB says pending but exchange says filled/cancelled
"""

import time
import logging
from datetime import datetime, timezone

from ..db import get_supabase
from ..config import settings
from . import binance_client
from .telegram_notifier import send_telegram

logger = logging.getLogger(__name__)


async def run_reconciliation() -> dict:
    """Compare DB vs Binance and log divergences."""
    start = time.time()
    supabase = get_supabase()

    # 1. Create run record
    run_resp = supabase.table("reconciliation_runs").insert({
        "broker_adapter": f"spot_{settings.binance_env}",
        "status": "running",
    }).execute()
    run_id = run_resp.data[0]["id"] if run_resp.data else None

    divergences = []
    actions = []
    orders_synced = 0
    positions_synced = 0

    try:
        # 2. Fetch open orders from Binance
        exchange_orders = await binance_client.get_open_orders()
        exchange_order_ids = {o["orderId"] for o in exchange_orders}

        # 3. Fetch proposals that have a binance_order_id and are in active states
        active_resp = supabase.table("trade_proposals").select(
            "id, symbol, binance_order_id, status, type, quantity"
        ).not_.is_("binance_order_id", "null").in_(
            "status", ["executed", "approved"]
        ).execute()
        db_proposals = active_resp.data or []

        db_order_ids = {}
        for p in db_proposals:
            oid = p.get("binance_order_id")
            if oid:
                db_order_ids[int(oid)] = p

        # 4a. Detect orphan orders (on exchange but not in DB)
        for eo in exchange_orders:
            oid = eo["orderId"]
            if oid not in db_order_ids:
                divergences.append({
                    "type": "orphan",
                    "order_id": oid,
                    "symbol": eo.get("symbol"),
                    "side": eo.get("side"),
                    "status": eo.get("status"),
                    "detail": "Order exists on exchange but has no matching proposal in DB",
                })

        # 4b. Detect stale proposals (DB has order_id but exchange shows filled/cancelled)
        for oid, proposal in db_order_ids.items():
            if oid not in exchange_order_ids and proposal["status"] == "approved":
                # Order not open anymore — check actual status
                try:
                    order_status = await binance_client.get_order(
                        proposal["symbol"], oid
                    )
                    exchange_status = order_status.get("status", "UNKNOWN")
                    if exchange_status in ("FILLED", "CANCELED", "EXPIRED", "REJECTED"):
                        divergences.append({
                            "type": "stale",
                            "proposal_id": proposal["id"],
                            "order_id": oid,
                            "symbol": proposal["symbol"],
                            "db_status": proposal["status"],
                            "exchange_status": exchange_status,
                            "detail": f"Proposal approved but exchange order is {exchange_status}",
                        })
                except Exception as e:
                    logger.warning(f"Could not check order {oid}: {e}")

            orders_synced += 1

        # 5. Count open positions synced
        pos_resp = supabase.table("positions").select("id").eq("status", "open").execute()
        positions_synced = len(pos_resp.data or [])

        # 6. Get balance snapshot
        balance_snapshot = {}
        try:
            account = await binance_client.get_account()
            balance_snapshot = {
                b["asset"]: {
                    "free": float(b["free"]),
                    "locked": float(b["locked"]),
                }
                for b in account.get("balances", [])
                if float(b["free"]) > 0 or float(b["locked"]) > 0
            }
        except Exception as e:
            logger.warning(f"Could not fetch balance snapshot: {e}")

        duration_ms = int((time.time() - start) * 1000)

        # 7. Update run record
        if run_id:
            supabase.table("reconciliation_runs").update({
                "orders_synced": orders_synced,
                "positions_synced": positions_synced,
                "divergences_found": len(divergences),
                "divergence_details": divergences,
                "actions_taken": actions,
                "balance_snapshot": balance_snapshot,
                "status": "success",
                "duration_ms": duration_ms,
            }).eq("id", run_id).execute()

        # 8. Alert on divergences
        if divergences:
            msg = (
                f"<b>RECONCILIATION ALERT</b>\n"
                f"Divergences found: <b>{len(divergences)}</b>\n\n"
            )
            for d in divergences[:5]:
                msg += f"- [{d['type'].upper()}] {d.get('symbol', '?')}: {d.get('detail', '')}\n"
            if len(divergences) > 5:
                msg += f"\n... and {len(divergences) - 5} more"
            await send_telegram(msg)

        result = {
            "run_id": run_id,
            "orders_synced": orders_synced,
            "positions_synced": positions_synced,
            "divergences_found": len(divergences),
            "divergences": divergences,
            "duration_ms": duration_ms,
            "status": "success",
        }
        if divergences:
            logger.warning(f"Reconciliation found {len(divergences)} divergences")
        else:
            logger.info(f"Reconciliation OK ({duration_ms}ms, {orders_synced} orders, {positions_synced} positions)")

        return result

    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        logger.error(f"Reconciliation error: {e}")
        if run_id:
            supabase.table("reconciliation_runs").update({
                "status": "error",
                "error_message": str(e),
                "duration_ms": duration_ms,
            }).eq("id", run_id).execute()
        return {
            "run_id": run_id,
            "status": "error",
            "error": str(e),
            "duration_ms": duration_ms,
        }


async def get_latest_reconciliation() -> dict | None:
    """Get the most recent reconciliation run."""
    supabase = get_supabase()
    resp = supabase.table("reconciliation_runs").select("*").order(
        "created_at", desc=True
    ).limit(1).execute()
    return resp.data[0] if resp.data else None


async def get_reconciliation_history(limit: int = 20) -> list:
    """Get recent reconciliation runs."""
    supabase = get_supabase()
    resp = supabase.table("reconciliation_runs").select("*").order(
        "created_at", desc=True
    ).limit(limit).execute()
    return resp.data or []
