"""Tests para binance_client.get_klines — debe bypassear el proxy siempre.

Evidencia 2026-07-14: el proxy binance.italicia.com (ya auditado 2x por
precios stale/drifted, ver get_price_direct/get_price_verified) también
sirve klines con high/low corruptos. get_klines() ahora pega SIEMPRE
directo a testnet.binance.vision, sin importar la config de proxy.
"""

import pytest
from unittest.mock import AsyncMock, patch


class _FakeResponse:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


class _FakeAsyncClient:
    """Stand-in para httpx.AsyncClient que registra la URL pedida."""

    last_url = None
    last_params = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None):
        _FakeAsyncClient.last_url = url
        _FakeAsyncClient.last_params = params
        return _FakeResponse([[1700000000000, "1800", "1810", "1795", "1805",
                                "50", 1700003600000, "91000", "800", "25", "45500", "0"]])


@pytest.mark.asyncio
async def test_get_klines_always_hits_direct_base_even_when_proxy_configured():
    from app.services import binance_client

    with patch.object(binance_client, "USE_PROXY", True), \
         patch.object(binance_client, "PROXY_BASE", "https://binance.italicia.com/binance"), \
         patch.object(binance_client, "httpx") as mock_httpx:
        mock_httpx.AsyncClient = _FakeAsyncClient
        await binance_client.get_klines("ETHUSDT", "1h", limit=5)

    assert _FakeAsyncClient.last_url == f"{binance_client.DIRECT_BASE}/api/v3/klines"
    assert "italicia" not in _FakeAsyncClient.last_url


@pytest.mark.asyncio
async def test_get_klines_passes_through_params():
    from app.services import binance_client

    with patch.object(binance_client, "httpx") as mock_httpx:
        mock_httpx.AsyncClient = _FakeAsyncClient
        await binance_client.get_klines("BTCUSDT", "4h", limit=10, start_time=123, end_time=456)

    assert _FakeAsyncClient.last_params == {
        "symbol": "BTCUSDT", "interval": "4h", "limit": 10,
        "startTime": 123, "endTime": 456,
    }
