import hashlib
import hmac
import time
import httpx
from typing import Optional
from ..config import settings
import logging

logger = logging.getLogger(__name__)

DIRECT_BASE = "https://testnet.binance.vision"
USE_PROXY = bool(settings.binance_proxy_url and settings.binance_proxy_auth_secret)
PROXY_BASE = settings.binance_proxy_url.rstrip("/") + "/binance" if settings.binance_proxy_url else None


def _sign(params: dict, secret: str) -> str:
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return hmac.new(
        secret.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _headers(signed: bool = False, use_proxy: Optional[bool] = None) -> dict:
    proxy_mode = USE_PROXY if use_proxy is None else use_proxy
    if proxy_mode:
        return {
            "Authorization": f"Bearer {settings.binance_proxy_auth_secret}",
            "Content-Type": "application/json",
        }

    headers = {"Content-Type": "application/json"}
    if signed:
        headers["X-MBX-APIKEY"] = settings.binance_testnet_api_key
    return headers


async def _request(
    method: str,
    endpoint: str,
    params: dict,
    timeout: int,
    signed: bool = False,
) -> dict | list:
    """Request helper with proxy->direct fallback when proxy auth/connectivity fails."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        if USE_PROXY and PROXY_BASE:
            try:
                proxy_resp = await client.request(
                    method,
                    f"{PROXY_BASE}{endpoint}",
                    params=params,
                    headers=_headers(signed=signed, use_proxy=True),
                )
                proxy_resp.raise_for_status()
                return proxy_resp.json()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                # Common proxy auth failure. Retry direct.
                if status in (401, 403):
                    logger.warning(f"Proxy returned {status} for {endpoint}, falling back to direct testnet")
                else:
                    raise
            except httpx.RequestError as e:
                logger.warning(f"Proxy request error for {endpoint} ({e}), falling back to direct testnet")

        direct_resp = await client.request(
            method,
            f"{DIRECT_BASE}{endpoint}",
            params=params,
            headers=_headers(signed=signed, use_proxy=False),
        )
        direct_resp.raise_for_status()
        return direct_resp.json()


async def get_price(symbol: str) -> dict:
    return await _request(
        method="GET",
        endpoint="/api/v3/ticker/price",
        params={"symbol": symbol},
        timeout=10,
        signed=False,
    )


async def get_account() -> dict:
    params = {"timestamp": int(time.time() * 1000)}
    params["signature"] = _sign(params, settings.binance_testnet_secret)
    return await _request(
        method="GET",
        endpoint="/api/v3/account",
        params=params,
        timeout=15,
        signed=True,
    )


async def get_ticker_24hr(symbol: str) -> dict:
    return await _request(
        method="GET",
        endpoint="/api/v3/ticker/24hr",
        params={"symbol": symbol},
        timeout=10,
        signed=False,
    )


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

    return await _request(
        method="POST",
        endpoint="/api/v3/order",
        params=params,
        timeout=20,
        signed=True,
    )


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
    return await _request(
        method="GET",
        endpoint="/api/v3/klines",
        params=params,
        timeout=15,
        signed=False,
    )


async def get_order(symbol: str, order_id: int) -> dict:
    params = {
        "symbol": symbol,
        "orderId": order_id,
        "timestamp": int(time.time() * 1000),
    }
    params["signature"] = _sign(params, settings.binance_testnet_secret)
    return await _request(
        method="GET",
        endpoint="/api/v3/order",
        params=params,
        timeout=10,
        signed=True,
    )


async def get_open_orders(symbol: Optional[str] = None) -> list:
    """Fetch all open orders, optionally filtered by symbol."""
    params: dict = {"timestamp": int(time.time() * 1000)}
    if symbol:
        params["symbol"] = symbol
    params["signature"] = _sign(params, settings.binance_testnet_secret)
    return await _request(
        method="GET",
        endpoint="/api/v3/openOrders",
        params=params,
        timeout=15,
        signed=True,
    )


async def cancel_order(symbol: str, order_id: int) -> dict:
    """Cancel an open order."""
    params = {
        "symbol": symbol,
        "orderId": order_id,
        "timestamp": int(time.time() * 1000),
    }
    params["signature"] = _sign(params, settings.binance_testnet_secret)
    return await _request(
        method="DELETE",
        endpoint="/api/v3/order",
        params=params,
        timeout=10,
        signed=True,
    )
