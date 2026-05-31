"""Tools de IOL expuestas al Claude Agent SDK como MCP server in-process.

Lecturas: libres. Escrituras (place_buy/place_sell/cancel): pasan SIEMPRE por el
gate de confirmación (via can_use_tool) antes de ejecutarse.

NOTA: `@tool` y `create_sdk_mcp_server` provienen de `claude-agent-sdk`. La firma
exacta puede variar entre versiones; verificar al instalar.
"""
from __future__ import annotations

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool  # type: ignore

from ..analytics.metrics import compute_metrics
from ..iol.client import IOLClient, IOLError
from ..iol.models import OrderRequest


def _text(s: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": s}]}


def _err(s: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": s}], "is_error": True}


def build_iol_server(client: IOLClient):
    """Construye el MCP server in-process con las tools de IOL (closures sobre client)."""

    @tool("get_portfolio", "Trae la cartera actual del usuario en IOL (tenencias).", {"pais": str})
    async def get_portfolio(args: dict) -> dict:
        try:
            p = await client.get_portfolio(args.get("pais", "argentina"))
        except IOLError as e:
            return _err(f"No se pudo traer la cartera: {e}")
        lines = [
            f"- {h.simbolo}: {h.cantidad} @ {h.ultimo_precio} = {h.valorizado} {h.moneda}"
            f"{f' ({h.ganancia_porcentaje:+.1f}%)' if h.ganancia_porcentaje is not None else ''}"
            for h in p.holdings
        ]
        return _text(f"Cartera ({p.pais}), total {p.total_valorizado}:\n" + "\n".join(lines))

    @tool("get_account_state", "Trae saldos y disponible por moneda en IOL.", {})
    async def get_account_state(args: dict) -> dict:
        try:
            cuentas = await client.get_account_state()
        except IOLError as e:
            return _err(f"No se pudo traer el estado de cuenta: {e}")
        lines = [
            f"- {c.moneda}: disponible {c.disponible}, comprometido {c.comprometido}, total {c.total}"
            for c in cuentas
        ]
        return _text("Estado de cuenta:\n" + "\n".join(lines))

    @tool("get_metrics", "Calcula métricas de la cartera: allocation %, cash %, concentración.", {"pais": str})
    async def get_metrics(args: dict) -> dict:
        try:
            p = await client.get_portfolio(args.get("pais", "argentina"))
            cuentas = await client.get_account_state()
        except IOLError as e:
            return _err(f"No se pudieron calcular métricas: {e}")
        m = compute_metrics(p, cuentas)
        return _text(
            f"Métricas:\n"
            f"- Total (invertido+cash): {m.total_valorizado}\n"
            f"- Cash: {m.cash_total} ({m.cash_pct}%)\n"
            f"- Concentración top: {m.top_symbol} {m.top_concentration_pct}%\n"
            f"- Allocation: {m.allocation_pct}"
        )

    @tool("get_quote", "Cotización de un título.", {"mercado": str, "simbolo": str})
    async def get_quote(args: dict) -> dict:
        try:
            q = await client.get_quote(args["mercado"], args["simbolo"])
        except IOLError as e:
            return _err(f"No se pudo traer la cotización: {e}")
        return _text(f"{q.simbolo} ({q.mercado}): último {q.ultimo}, compra {q.compra}, venta {q.venta}")

    @tool(
        "place_buy",
        "Propone una orden de COMPRA. Requiere confirmación humana antes de ejecutarse.",
        {"mercado": str, "simbolo": str, "cantidad": float, "precio": float, "plazo": str},
    )
    async def place_buy(args: dict) -> dict:
        return await _place(client, args, "comprar")

    @tool(
        "place_sell",
        "Propone una orden de VENTA. Requiere confirmación humana antes de ejecutarse.",
        {"mercado": str, "simbolo": str, "cantidad": float, "precio": float, "plazo": str},
    )
    async def place_sell(args: dict) -> dict:
        return await _place(client, args, "vender")

    return create_sdk_mcp_server(
        name="iol",
        version="0.1.0",
        tools=[get_portfolio, get_account_state, get_metrics, get_quote, place_buy, place_sell],
    )


async def _place(client: IOLClient, args: dict, tipo: str) -> dict:
    # Si llegó hasta acá, el gate ya aprobó (via can_use_tool). Ejecuta en IOL.
    try:
        result = await client.place_order(
            OrderRequest(
                mercado=args["mercado"],
                simbolo=args["simbolo"],
                cantidad=float(args["cantidad"]),
                precio=float(args["precio"]),
                tipo=tipo,
                plazo=args.get("plazo", "t1"),
            )
        )
    except IOLError as e:
        return _err(f"La orden NO se ejecutó (error de IOL): {e}")
    if not result.ok:
        return _err(f"IOL rechazó la orden: {result.mensaje}")
    return _text(f"✅ Orden enviada. N° {result.numero_operacion}. Estado: {result.mensaje}")
