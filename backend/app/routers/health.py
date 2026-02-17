from fastapi import APIRouter
from ..db import get_supabase
from ..services import binance_client
from ..config import settings

router = APIRouter()


@router.get("/health")
async def health():
    checks = {}

    # Supabase check
    try:
        get_supabase().table("trade_proposals").select("id").limit(1).execute()
        checks["supabase"] = "ok"
    except Exception as e:
        checks["supabase"] = f"error: {e}"

    # Binance check
    try:
        await binance_client.get_price("BTCUSDT")
        checks["binance"] = "ok"
    except Exception as e:
        checks["binance"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
        "env": settings.binance_env,
        "proxy": settings.binance_proxy_url,
    }
