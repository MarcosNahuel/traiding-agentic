"""Daily report service — generates and sends a Telegram summary."""

import logging
from datetime import datetime, timezone, timedelta

from ..db import get_supabase
from ..config import settings
from . import binance_client
from .telegram_notifier import send_telegram

logger = logging.getLogger(__name__)

# Track whether we already sent today's report
_last_report_date: str | None = None


def already_sent_today() -> bool:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _last_report_date == today


async def send_daily_report() -> dict:
    """Generate and send a daily trading report via Telegram."""
    global _last_report_date
    supabase = get_supabase()
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_iso = today_start.isoformat()

    # 1. Balance
    total_balance = 0.0
    try:
        account = await binance_client.get_account()
        for b in account.get("balances", []):
            if b["asset"] == "USDT":
                total_balance = float(b["free"]) + float(b["locked"])
                break
    except Exception as e:
        logger.warning(f"Could not fetch balance: {e}")

    # 2. Closed positions today
    try:
        closed_resp = supabase.table("positions").select("*").eq(
            "status", "closed"
        ).gte("closed_at", today_iso).execute()
        closed_today = closed_resp.data or []
    except Exception:
        closed_today = []

    winners = [p for p in closed_today if float(p.get("realized_pnl", 0)) > 0]
    losers = [p for p in closed_today if float(p.get("realized_pnl", 0)) <= 0]
    daily_pnl = sum(float(p.get("realized_pnl", 0)) for p in closed_today)

    # 3. Errors today
    try:
        err_resp = supabase.table("trade_proposals").select("id", count="exact").in_(
            "status", ["error", "dead_letter"]
        ).gte("updated_at", today_iso).execute()
        errors_today = err_resp.count or 0
    except Exception:
        errors_today = 0

    # 4. Dead letters pending
    try:
        dl_resp = supabase.table("trade_proposals").select("id", count="exact").eq(
            "status", "dead_letter"
        ).execute()
        dead_letters = dl_resp.count or 0
    except Exception:
        dead_letters = 0

    # 5. Reconciliation divergences today
    try:
        recon_resp = supabase.table("reconciliation_runs").select(
            "divergences_found"
        ).gte("created_at", today_iso).execute()
        recon_runs = recon_resp.data or []
        total_divergences = sum(r.get("divergences_found", 0) for r in recon_runs)
        recon_count = len(recon_runs)
    except Exception:
        total_divergences = 0
        recon_count = 0

    # 6. System status
    pnl_emoji = "+" if daily_pnl >= 0 else ""
    status_line = "TRADING ENABLED" if settings.trading_enabled else "TRADING DISABLED"

    msg = (
        f"<b>DAILY REPORT</b> - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
        f"{'=' * 30}\n\n"
        f"<b>Balance:</b> ${total_balance:,.2f} USDT\n"
        f"<b>Daily PnL:</b> {pnl_emoji}${daily_pnl:,.4f}\n\n"
        f"<b>Trades closed today:</b> {len(closed_today)}\n"
        f"  Winners: {len(winners)} | Losers: {len(losers)}\n\n"
        f"<b>Errors today:</b> {errors_today}\n"
        f"<b>Dead letters pending:</b> {dead_letters}\n\n"
        f"<b>Reconciliation:</b> {recon_count} runs, {total_divergences} divergences\n\n"
        f"<b>Status:</b> {status_line}"
    )

    await send_telegram(msg)
    _last_report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return {
        "success": True,
        "balance": total_balance,
        "daily_pnl": daily_pnl,
        "trades_closed": len(closed_today),
        "errors_today": errors_today,
        "dead_letters": dead_letters,
        "recon_runs": recon_count,
        "divergences": total_divergences,
    }
