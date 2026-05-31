import httpx
import pytest

respx = pytest.importorskip("respx")

from asesor_iol.iol.client import IOLClient, IOLError


@respx.mock
async def test_auth_and_portfolio_parsing():
    respx.post("https://api.test/token").mock(
        return_value=httpx.Response(
            200, json={"access_token": "a", "refresh_token": "r", "expires_in": 900}
        )
    )
    respx.get("https://api.test/api/v2/portafolio/argentina").mock(
        return_value=httpx.Response(
            200,
            json={
                "activos": [
                    {
                        "titulo": {"simbolo": "SPY", "moneda": "dolar"},
                        "cantidad": 2,
                        "ultimoPrecio": 100,
                        "valorizado": 200,
                    }
                ]
            },
        )
    )
    async with IOLClient("u", "p", "https://api.test") as c:
        p = await c.get_portfolio()
    assert p.holdings[0].simbolo == "SPY"
    assert p.total_valorizado == 200


@respx.mock
async def test_auth_failure_raises():
    respx.post("https://api.test/token").mock(return_value=httpx.Response(400, text="bad"))
    async with IOLClient("u", "p", "https://api.test") as c:
        with pytest.raises(IOLError):
            await c.get_account_state()


@respx.mock
async def test_order_post_does_not_retry_on_error():
    respx.post("https://api.test/token").mock(
        return_value=httpx.Response(200, json={"access_token": "a", "expires_in": 900})
    )
    route = respx.post("https://api.test/api/v2/operar/Comprar").mock(
        return_value=httpx.Response(500, text="boom")
    )
    from asesor_iol.iol.models import OrderRequest

    async with IOLClient("u", "p", "https://api.test") as c:
        with pytest.raises(IOLError):
            await c.place_order(
                OrderRequest(mercado="bcba", simbolo="SPY", cantidad=1, precio=1, tipo="comprar")
            )
    assert route.call_count == 1  # NO reintenta una orden
