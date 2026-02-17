import hashlib
import hmac
import time
import httpx
from typing import Optional
from ..config import settings
import logging

logger = logging.getLogger(__name__)

PROXY_BASE = settings.binance_proxy_url.rstrip("/") + "/binance"


def _sign(params: dict, secret: str) -> str:
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return hmac.new(
        secret.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.binance_proxy_auth_secret}",
        "Content-Type": "application/json",
    }


async def get_price(symbol: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{PROXY_BASE}/api/v3/ticker/price",
            params={"symbol": symbol},
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def get_account() -> dict:
    params = {"timestamp": int(time.time() * 1000)}
    params["signature"] = _sign(params, settings.binance_testnet_secret)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{PROXY_BASE}/api/v3/account",
            params=params,
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def get_ticker_24hr(symbol: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{PROXY_BASE}/api/v3/ticker/24hr",
            params={"symbol": symbol},
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def place_order(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float] = None,
) -> dict:
    params: dict = {
        "symbol": symbol,
        "side": side.upper(),
        "type": order_type.upper(),
        "quantity": str(quantity),
        "timestamp": int(time.time() * 1000),
    }
    if order_type.upper() == "LIMIT" and price:
        params["price"] = str(price)
        params["timeInForce"] = "GTC"

    params["signature"] = _sign(params, settings.binance_testnet_secret)

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{PROXY_BASE}/api/v3/order",
            params=params,
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def get_klines(
    symbol: str,
    interval: str = "1h",
    limit: int = 500,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
) -> list:
    """Fetch OHLCV kline/candlestick data from Binance."""
    params: dict = {"symbol": symbol, "interval": interval, "limit": limit}
    if start_time:
        params["startTime"] = start_time
    if end_time:
        params["endTime"] = end_time
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{PROXY_BASE}/api/v3/klines",
            params=params,
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def get_order(symbol: str, order_id: int) -> dict:
    params = {
        "symbol": symbol,
        "orderId": order_id,
        "timestamp": int(time.time() * 1000),
    }
    params["signature"] = _sign(params, settings.binance_testnet_secret)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{PROXY_BASE}/api/v3/order",
            params=params,
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()
