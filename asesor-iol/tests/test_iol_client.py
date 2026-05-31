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


def _auth_mock():
    return respx.post("https://api.test/token").mock(
        return_value=httpx.Response(200, json={"access_token": "a", "expires_in": 900})
    )


@respx.mock
async def test_get_panel_parsing():
    _auth_mock()
    respx.get("https://api.test/api/v2/Cotizaciones/cedears/Todos/argentina").mock(
        return_value=httpx.Response(
            200,
            json={"titulos": [
                {"simbolo": "AAPL", "ultimoPrecio": 1000, "variacionPorcentual": 1.5},
                {"simbolo": "MSFT", "ultimoPrecio": 2000},
            ]},
        )
    )
    async with IOLClient("u", "p", "https://api.test") as c:
        rows = await c.get_panel("cedears", "Todos")
    assert rows[0].simbolo == "AAPL" and rows[0].variacion_pct == 1.5
    assert rows[1].variacion_pct is None


@respx.mock
async def test_get_options_parsing():
    _auth_mock()
    respx.get("https://api.test/api/v2/bCBA/Titulos/GGAL/Opciones").mock(
        return_value=httpx.Response(
            200,
            json=[{"simbolo": "GFGC100", "tipoOpcion": "call", "precioEjercicio": 100,
                   "fechaVencimiento": "2026-06-20", "ultimoPrecio": 5.2}],
        )
    )
    async with IOLClient("u", "p", "https://api.test") as c:
        opts = await c.get_options("bCBA", "GGAL")
    assert opts[0].tipo == "call" and opts[0].strike == 100 and opts[0].subyacente == "GGAL"


@respx.mock
async def test_get_historical_parsing():
    _auth_mock()
    respx.get(
        "https://api.test/api/v2/bCBA/Titulos/SPY/Cotizacion/seriehistorica/2026-01-01/2026-01-31/ajustada"
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {"fechaHora": "2026-01-01", "apertura": 100, "maximo": 110, "minimo": 95, "ultimoPrecio": 105},
                {"fechaHora": "2026-01-31", "apertura": 105, "maximo": 120, "minimo": 100, "ultimoPrecio": 118},
            ],
        )
    )
    async with IOLClient("u", "p", "https://api.test") as c:
        bars = await c.get_historical("bCBA", "SPY", "2026-01-01", "2026-01-31")
    assert len(bars) == 2 and bars[0].cierre == 105 and bars[-1].cierre == 118


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
