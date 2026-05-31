"""Cliente async de la API de InvertirOnline (IOL).

Auth: OAuth2 password grant. El access token dura ~15 min y se renueva con
refresh_token. Esta clase maneja el refresh automáticamente.

NOTA: los paths exactos de los endpoints (/api/v2/...) deben verificarse contra
el Swagger vivo (https://api.invertironline.com/) antes de operar en real. Acá se
usan los documentados/observados en la investigación. El sandbox de homologación
(api.homo.invertironline.com) sirve para lecturas; las escrituras están en BETA.
"""
from __future__ import annotations

import asyncio
import time

import httpx

from .models import (
    AccountState,
    HistoricalBar,
    Holding,
    InstrumentRow,
    OptionContract,
    OrderRequest,
    OrderResult,
    Portfolio,
    Quote,
)


class IOLError(RuntimeError):
    """Error de la API de IOL. Nunca se interpreta como éxito."""


class IOLClient:
    def __init__(
        self,
        username: str,
        password: str,
        api_base: str = "https://api.invertironline.com",
        *,
        timeout: float = 30.0,
    ) -> None:
        self._username = username
        self._password = password
        self._base = api_base.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._base, timeout=timeout)
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "IOLClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # ---- Autenticación -------------------------------------------------
    async def _authenticate(self) -> None:
        resp = await self._client.post(
            "/token",
            data={
                "username": self._username,
                "password": self._password,
                "grant_type": "password",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self._store_token(resp)

    async def _refresh(self) -> None:
        if not self._refresh_token:
            await self._authenticate()
            return
        resp = await self._client.post(
            "/token",
            data={
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code >= 400:
            # El refresh falló: reautenticar desde cero (no asumir nada).
            await self._authenticate()
            return
        self._store_token(resp)

    def _store_token(self, resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            raise IOLError(f"Auth falló ({resp.status_code}): {resp.text[:200]}")
        data = resp.json()
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        # margen de 60s antes del vencimiento real (~900s).
        self._expires_at = time.monotonic() + int(data.get("expires_in", 900)) - 60

    async def _ensure_token(self) -> str:
        async with self._lock:
            if self._access_token is None:
                await self._authenticate()
            elif time.monotonic() >= self._expires_at:
                await self._refresh()
            assert self._access_token is not None
            return self._access_token

    async def _get(self, path: str) -> dict:
        token = await self._ensure_token()
        resp = await self._client.get(
            path, headers={"Authorization": f"Bearer {token}"}
        )
        if resp.status_code == 401:
            # token caído: refrescar una vez y reintentar (lectura, idempotente).
            await self._refresh()
            token = self._access_token or await self._ensure_token()
            resp = await self._client.get(
                path, headers={"Authorization": f"Bearer {token}"}
            )
        if resp.status_code >= 400:
            raise IOLError(f"GET {path} -> {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    async def _post(self, path: str, json: dict) -> dict:
        """POST para escrituras. NO reintenta automáticamente (riesgo de
        doble-ejecución de una orden). Si falla, propaga el error."""
        token = await self._ensure_token()
        resp = await self._client.post(
            path, json=json, headers={"Authorization": f"Bearer {token}"}
        )
        if resp.status_code >= 400:
            raise IOLError(f"POST {path} -> {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    # ---- Lecturas ------------------------------------------------------
    async def get_portfolio(self, pais: str = "argentina") -> Portfolio:
        data = await self._get(f"/api/v2/portafolio/{pais}")
        holdings = [
            Holding(
                simbolo=a.get("titulo", {}).get("simbolo", a.get("simbolo", "?")),
                cantidad=float(a.get("cantidad", 0)),
                ultimo_precio=float(a.get("ultimoPrecio", 0)),
                valorizado=float(a.get("valorizado", 0)),
                moneda=a.get("titulo", {}).get("moneda", "peso_Argentino"),
                ppc=_maybe_float(a.get("ppc")),
                ganancia_porcentaje=_maybe_float(a.get("gananciaPorcentaje")),
            )
            for a in data.get("activos", [])
        ]
        return Portfolio(pais=pais, holdings=holdings)

    async def get_account_state(self) -> list[AccountState]:
        data = await self._get("/api/v2/estadocuenta")
        out: list[AccountState] = []
        for cuenta in data.get("cuentas", []):
            out.append(
                AccountState(
                    moneda=cuenta.get("moneda", "?"),
                    disponible=float(cuenta.get("disponible", 0)),
                    comprometido=float(cuenta.get("comprometido", 0)),
                    titulos_valorizados=float(cuenta.get("titulosValorizados", 0)),
                    total=float(cuenta.get("total", 0)),
                )
            )
        return out

    async def get_quote(self, mercado: str, simbolo: str) -> Quote:
        data = await self._get(f"/api/v2/{mercado}/Titulos/{simbolo}/Cotizacion")
        return Quote(
            simbolo=simbolo,
            mercado=mercado,
            ultimo=float(data.get("ultimoPrecio", 0)),
            compra=_maybe_float(data.get("puntas", [{}])[0].get("precioCompra"))
            if data.get("puntas")
            else None,
            venta=_maybe_float(data.get("puntas", [{}])[0].get("precioVenta"))
            if data.get("puntas")
            else None,
            moneda=data.get("moneda"),
        )

    async def get_panel(
        self, instrumento: str, panel: str, pais: str = "argentina"
    ) -> list[InstrumentRow]:
        """Cotizaciones de un panel completo (ej. acciones/Merval, cedears/Todos).

        Sirve para que el subagente de datos liste universo y variaciones sin
        pedir título por título. Solo lectura.
        """
        data = await self._get(f"/api/v2/Cotizaciones/{instrumento}/{panel}/{pais}")
        titulos = data.get("titulos", data) if isinstance(data, dict) else data
        out: list[InstrumentRow] = []
        for t in titulos or []:
            out.append(
                InstrumentRow(
                    simbolo=t.get("simbolo", "?"),
                    ultimo=float(t.get("ultimoPrecio", 0) or 0),
                    variacion_pct=_maybe_float(t.get("variacionPorcentual")),
                    mercado=t.get("mercado"),
                    moneda=t.get("moneda"),
                )
            )
        return out

    async def get_options(self, mercado: str, simbolo: str) -> list[OptionContract]:
        """Chain de opciones de un subyacente. Solo lectura.

        IOL no expone greeks ni volatilidad implícita: devuelve los contratos
        (strike, vencimiento, último). Los greeks, si se quisieran, se calcularían
        en una capa de analytics propia sobre estos datos.
        """
        data = await self._get(f"/api/v2/{mercado}/Titulos/{simbolo}/Opciones")
        items = data.get("opciones", data) if isinstance(data, dict) else data
        out: list[OptionContract] = []
        for o in items or []:
            out.append(
                OptionContract(
                    simbolo=o.get("simbolo", "?"),
                    tipo=o.get("tipoOpcion") or o.get("tipo"),
                    strike=_maybe_float(o.get("precioEjercicio") or o.get("strike")),
                    vencimiento=o.get("fechaVencimiento") or o.get("vencimiento"),
                    ultimo=_maybe_float(o.get("ultimoPrecio")),
                    subyacente=simbolo,
                )
            )
        return out

    async def get_historical(
        self,
        mercado: str,
        simbolo: str,
        fecha_desde: str,
        fecha_hasta: str,
        ajustada: str = "ajustada",
    ) -> list[HistoricalBar]:
        """Serie histórica OHLC entre dos fechas (YYYY-MM-DD). Solo lectura."""
        path = (
            f"/api/v2/{mercado}/Titulos/{simbolo}/Cotizacion/seriehistorica/"
            f"{fecha_desde}/{fecha_hasta}/{ajustada}"
        )
        data = await self._get(path)
        bars = data if isinstance(data, list) else data.get("series", [])
        out: list[HistoricalBar] = []
        for b in bars or []:
            out.append(
                HistoricalBar(
                    fecha=str(b.get("fechaHora") or b.get("fecha") or "?"),
                    apertura=_maybe_float(b.get("apertura")),
                    maximo=_maybe_float(b.get("maximo")),
                    minimo=_maybe_float(b.get("minimo")),
                    cierre=_maybe_float(b.get("ultimoPrecio") or b.get("cierre")),
                    volumen=_maybe_float(b.get("volumenNominal") or b.get("volumen")),
                )
            )
        return out

    # ---- Escrituras (siempre detrás del gate de confirmación) ----------
    async def place_order(self, order: OrderRequest) -> OrderResult:
        endpoint = "Comprar" if order.tipo == "comprar" else "Vender"
        body = {
            "mercado": order.mercado,
            "simbolo": order.simbolo,
            "cantidad": order.cantidad,
            "precio": order.precio,
            "plazo": order.plazo,
        }
        if order.validez:
            body["validez"] = order.validez
        data = await self._post(f"/api/v2/operar/{endpoint}", body)
        return OrderResult(
            ok=bool(data.get("ok", True)),
            numero_operacion=str(data.get("numeroOperacion"))
            if data.get("numeroOperacion") is not None
            else None,
            mensaje=data.get("messageLevel") or data.get("mensaje") or "enviada",
            raw=data,
        )


def _maybe_float(v: object) -> float | None:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
