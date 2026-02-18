from fastapi import APIRouter
from datetime import datetime, timezone, timedelta
from ..db import get_supabase
from ..services import binance_client
from ..services.telegram_notifier import is_telegram_configured
from ..config import settings

router = APIRouter()


@router.get("/health")
async def health():
    checks = {}
    metrics = {}

    # Database check
    try:
        get_supabase().table("trade_proposals").select("id").limit(1).execute()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Binance REST check
    try:
        await binance_client.get_price("BTCUSDT")
        checks["binance_rest"] = "ok"
    except Exception as e:
        checks["binance_rest"] = f"error: {e}"

    # Telegram check
    checks["telegram"] = "ok" if is_telegram_configured() else "not_configured"

    # Reconciliation staleness check
    try:
        supabase = get_supabase()
        recon_resp = supabase.table("reconciliation_runs").select(
            "id, created_at, status, divergences_found"
        ).order("created_at", desc=True).limit(1).execute()
        if recon_resp.data:
            last_recon = recon_resp.data[0]
            last_recon_time = datetime.fromisoformat(last_recon["created_at"].replace("Z", "+00:00"))
            staleness = (datetime.now(timezone.utc) - last_recon_time).total_seconds()
            if staleness > 300:  # >5 min stale
                checks["reconciliation"] = f"stale ({int(staleness)}s ago)"
            else:
                checks["reconciliation"] = "ok"
            metrics["last_recon"] = last_recon["created_at"]
            metrics["last_recon_divergences"] = last_recon["divergences_found"]
        else:
            checks["reconciliation"] = "no_runs"
    except Exception as e:
        checks["reconciliation"] = f"error: {e}"

    # Dead letters count
    try:
        dl_resp = supabase.table("trade_proposals").select("id", count="exact").eq(
            "status", "dead_letter"
        ).execute()
        metrics["dead_letters"] = dl_resp.count or 0
    except Exception:
        metrics["dead_letters"] = -1

    # Total balance
    try:
        account = await binance_client.get_account()
        usdt_balance = next(
            (float(b["free"]) + float(b["locked"]) for b in account.get("balances", []) if b["asset"] == "USDT"),
            0.0,
        )
        metrics["total_balance_usdt"] = usdt_balance
    except Exception:
        metrics["total_balance_usdt"] = None

    # Daily PnL (closed positions today)
    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        pnl_resp = supabase.table("positions").select("realized_pnl").eq(
            "status", "closed"
        ).gte("closed_at", today_start).execute()
        daily_pnl = sum(float(p.get("realized_pnl", 0)) for p in (pnl_resp.data or []))
        metrics["daily_pnl"] = daily_pnl
    except Exception:
        metrics["daily_pnl"] = None

    # Determine overall status
    error_checks = [v for v in checks.values() if isinstance(v, str) and v.startswith("error")]
    if error_checks:
        overall = "unhealthy"
    elif any(v not in ("ok", "not_configured") for v in checks.values()):
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "trading_enabled": settings.trading_enabled,
        "checks": checks,
        "metrics": metrics,
        "env": settings.binance_env,
        "proxy": settings.binance_proxy_url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
