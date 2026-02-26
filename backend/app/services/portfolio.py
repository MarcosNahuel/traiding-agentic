from datetime import date, datetime, timezone
from ..db import get_supabase
from . import binance_client
import logging

logger = logging.getLogger(__name__)


async def get_portfolio_state() -> dict:
    supabase = get_supabase()

    # Binance balances
    usdt_free = 0.0
    try:
        account = await binance_client.get_account()
        balances = {b["asset"]: float(b["free"]) + float(b["locked"]) for b in account.get("balances", [])}
        usdt_free = float(next((b["free"] for b in account.get("balances", []) if b["asset"] == "USDT"), 0))
    except Exception as e:
        logger.warning(f"Could not fetch Binance account: {e}")

    # Open and partially closed positions
    pos_resp = supabase.table("positions").select("*").in_("status", ["open", "partially_closed"]).execute()
    positions = pos_resp.data or []

    # Update current prices for open positions
    in_positions = 0.0
    unrealized_pnl = 0.0
    updated_positions = []
    for pos in positions:
        try:
            ticker = await binance_client.get_price(pos["symbol"])
            current_price = float(ticker.get("price", pos["current_price"]))
            entry_price = float(pos["entry_price"])
            current_qty = float(pos["current_quantity"])
            commission = float(pos.get("total_commission", 0))

            upnl = (current_price - entry_price) * current_qty - commission
            upnl_pct = (upnl / (entry_price * current_qty)) * 100 if entry_price * current_qty > 0 else 0

            in_positions += current_price * current_qty
            unrealized_pnl += upnl

            # Update DB with current price (use updated_at for optimistic concurrency)
            now_iso = datetime.now(timezone.utc).isoformat()
            supabase.table("positions").update({
                "current_price": current_price,
                "unrealized_pnl": upnl,
                "unrealized_pnl_percent": upnl_pct,
                "updated_at": now_iso,
            }).eq("id", pos["id"]).in_("status", ["open", "partially_closed"]).execute()

            updated_positions.append({
                **pos,
                "current_price": current_price,
                "unrealized_pnl": upnl,
                "unrealized_pnl_percent": upnl_pct,
                "display": f"{'LONG' if pos['side']=='long' else 'SHORT'} {pos['current_quantity']} {pos['symbol']} @ {pos['entry_price']} | uPnL: ${upnl:.4f} ({upnl_pct:.2f}%)"
            })
        except Exception as e:
            logger.warning(f"Could not update position {pos['symbol']}: {e}")
            in_positions += float(pos.get("entry_notional", 0))
            updated_positions.append(pos)

    total_portfolio = usdt_free + in_positions

    # Performance stats from closed positions
    closed_resp = supabase.table("positions").select("realized_pnl, closed_at").eq("status", "closed").execute()
    closed = closed_resp.data or []
    all_time_pnl = sum(float(p.get("realized_pnl", 0)) for p in closed)
    total_trades = len(closed)
    winning = sum(1 for p in closed if float(p.get("realized_pnl", 0)) > 0)
    win_rate = (winning / total_trades * 100) if total_trades > 0 else 0.0

    # Daily PnL: realized from today's closed positions + unrealized from open
    today = date.today().isoformat()
    today_start = f"{today}T00:00:00Z"
    closed_today_resp = supabase.table("positions").select("realized_pnl").eq(
        "status", "closed"
    ).gte("closed_at", today_start).execute()
    realized_today = sum(float(p.get("realized_pnl", 0)) for p in (closed_today_resp.data or []))
    daily_pnl = realized_today + unrealized_pnl

    # Save snapshot
    try:
        existing = supabase.table("account_snapshots").select("id").eq("snapshot_date", today).execute()
        snap_data = {
            "snapshot_date": today,
            "total_balance": total_portfolio,
            "available_balance": usdt_free,
            "locked_balance": in_positions,
            "open_positions": len(positions),
            "daily_pnl": daily_pnl,
            "current_drawdown": 0.0,
            "peak_balance": total_portfolio,
        }
        if existing.data:
            supabase.table("account_snapshots").update(snap_data).eq("snapshot_date", today).execute()
        else:
            supabase.table("account_snapshots").insert(snap_data).execute()
    except Exception as e:
        logger.warning(f"Could not save snapshot: {e}")

    return {
        "usdt_balance": usdt_free,
        "total_portfolio_value": total_portfolio,
        "in_positions": in_positions,
        "open_positions": len(positions),
        "daily_pnl": daily_pnl,
        "all_time_pnl": all_time_pnl,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "unrealized_pnl": unrealized_pnl,
        "positions": updated_positions,
        "performance": {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "daily_pnl": daily_pnl,
            "all_time_pnl": all_time_pnl,
        }
    }
