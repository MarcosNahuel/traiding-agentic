"""Tests del wiring real del SDK (make_can_use_tool) — el invariante de seguridad
se prueba en el callback que el Claude Agent SDK invoca, no solo en gate.evaluate.
(jury: Claude flagged que faltaba cobertura de este path.)
"""
from asesor_iol.security.gate import ApprovalBroker, ConfirmationGate
from asesor_iol.security.hooks import make_can_use_tool
from asesor_iol.state.store import Store

from _helpers import make_settings


def _is_deny(res) -> bool:
    if isinstance(res, dict):
        return res.get("behavior") == "deny"
    return type(res).__name__ == "PermissionResultDeny"


def _gate(tmp_path, send, **over):
    settings = make_settings(tmp_path, **over)
    store = Store(settings.state_db_path)
    gate = ConfirmationGate(settings, store, ApprovalBroker(), send)
    return gate, store


async def test_can_use_tool_denies_when_gate_denies(tmp_path):
    async def send(oid, summary):
        pass

    gate, store = _gate(tmp_path, send, max_order_amount=100.0)
    cb = make_can_use_tool(gate)
    res = await cb(
        "mcp__iol__place_buy",
        {"simbolo": "SPY", "mercado": "bcba", "cantidad": 10, "precio": 50},  # 500 > 100
    )
    assert _is_deny(res)
    store.close()


async def test_can_use_tool_allows_read_tools(tmp_path):
    async def send(oid, summary):
        raise AssertionError("una lectura no debería pedir confirmación")

    gate, store = _gate(tmp_path, send)
    cb = make_can_use_tool(gate)
    res = await cb("mcp__iol__get_portfolio", {})
    assert not _is_deny(res)
    store.close()


async def test_can_use_tool_denies_unknown_write(tmp_path):
    async def send(oid, summary):
        pass

    gate, store = _gate(tmp_path, send)
    cb = make_can_use_tool(gate)
    res = await cb("mcp__iol__place_short", {"simbolo": "SPY", "mercado": "bcba", "cantidad": 1, "precio": 1})
    assert _is_deny(res)  # F8: drift → deny-by-default, también vía el callback del SDK
    store.close()
