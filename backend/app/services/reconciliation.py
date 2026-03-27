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
from .telegram_notifier import escape_html, send_telegram

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
                try:
                    db_order_ids[int(oid)] = p
                except (ValueError, TypeError):
                    logger.warning(f"Invalid binance_order_id '{oid}' in proposal {p.get('id')}")

        # 4a. Detect orphan orders (on exchange but not in DB)
        for eo in exchange_orders:
            oid = eo.get("orderId")
            if not oid:
                logger.warning(f"Exchange order missing orderId: {eo}")
                continue
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
        pos_resp = supabase.table("positions").select("id, symbol, current_quantity").eq("status", "open").execute()
        open_positions = pos_resp.data or []
        positions_synced = len(open_positions)

        # 5b. Expire stale proposals (TTL >1h)
        try:
            expired = await _expire_stale_proposals(supabase)
            if expired > 0:
                actions.append({"type": "proposals_expired", "count": expired})
        except Exception as e:
            logger.warning("Proposal TTL cleanup failed: %s", e)

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

        # 6b. Cross-check DB positions vs Binance balances
        if balance_snapshot and open_positions:
            db_asset_qty = {}
            for p in open_positions:
                base = p["symbol"].replace("USDT", "").replace("BUSD", "")
                db_asset_qty[base] = db_asset_qty.get(base, 0) + float(p["current_quantity"])

            for asset, db_qty in db_asset_qty.items():
                binance_bal = balance_snapshot.get(asset, {})
                exchange_qty = binance_bal.get("free", 0) + binance_bal.get("locked", 0)
                diff = abs(db_qty - exchange_qty)
                tolerance = max(db_qty * 0.05, 0.0001)
                if diff > tolerance:
                    divergences.append({
                        "type": "balance_mismatch",
                        "symbol": f"{asset}USDT",
                        "detail": f"DB={db_qty:.6f} vs Exchange={exchange_qty:.6f} (diff={diff:.6f})",
                    })

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
                msg += (
                    f"- [{escape_html(d['type'].upper())}] "
                    f"{escape_html(d.get('symbol', '?'))}: "
                    f"{escape_html(d.get('detail', ''))}\n"
                )
            if len(divergences) > 5:
                msg += f"\n... and {len(divergences) - 5} more"
            sent = await send_telegram(msg)
            if not sent:
                logger.warning("Failed to send Telegram reconciliation alert")

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


async def _expire_stale_proposals(supabase) -> int:
    """Expire proposals older than 1 hour stuck in draft/validated/approved."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    stale_statuses = ["draft", "validated", "approved"]
    expired_count = 0

    for status in stale_statuses:
        resp = supabase.table("trade_proposals").select("id, symbol, type, status").eq(
            "status", status
        ).lt("created_at", cutoff).execute()

        for proposal in (resp.data or []):
            supabase.table("trade_proposals").update({
                "status": "rejected",
                "error_message": f"TTL expired: stuck in '{status}' for >1 hour",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", proposal["id"]).eq("status", status).execute()
            expired_count += 1
            logger.warning("Expired stale proposal %s (%s %s, was %s)",
                           proposal["id"][:8], proposal["type"], proposal["symbol"], status)

    return expired_count


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
