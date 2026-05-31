import pytest

from asesor_iol.security.gate import ApprovalBroker, ConfirmationGate
from asesor_iol.state.store import Store

from _helpers import make_settings


def _gate(tmp_path, send, **over):
    settings = make_settings(tmp_path, **over)
    store = Store(settings.state_db_path)
    broker = ApprovalBroker()
    gate = ConfirmationGate(settings, store, broker, send)
    return gate, store, broker


async def test_non_order_tool_is_allowed(tmp_path):
    async def send(oid, summary):
        raise AssertionError("no debería pedir confirmación para lecturas")

    gate, store, _ = _gate(tmp_path, send)
    d = await gate.evaluate("mcp__iol__get_portfolio", {})
    assert d.allow
    store.close()


async def test_amount_over_limit_denied_without_confirmation(tmp_path):
    called = False

    async def send(oid, summary):
        nonlocal called
        called = True

    gate, store, _ = _gate(tmp_path, send, max_order_amount=100.0)
    d = await gate.evaluate(
        "mcp__iol__place_buy",
        {"simbolo": "SPY", "mercado": "bcba", "cantidad": 10, "precio": 50},  # 500 > 100
    )
    assert not d.allow
    assert not called  # ni siquiera molesta al usuario
    store.close()


async def test_symbol_not_allowed_denied(tmp_path):
    async def send(oid, summary):
        pass

    gate, store, _ = _gate(tmp_path, send)
    d = await gate.evaluate(
        "mcp__iol__place_buy",
        {"simbolo": "DOGE", "mercado": "bcba", "cantidad": 1, "precio": 1},
    )
    assert not d.allow
    store.close()


async def test_pending_order_counts_toward_daily_limit(tmp_path):
    """F1 (jury): una orden pending ya comprometida debe contar para el tope diario."""
    async def send(oid, summary):
        pass

    gate, store, _ = _gate(tmp_path, send, max_daily_amount=100.0, order_confirmation_timeout_min=0)
    store.create_pending("existing", 1, {}, 80.0)  # 80 comprometidos (pending, sin ejecutar)
    d = await gate.evaluate(
        "mcp__iol__place_buy",
        {"simbolo": "SPY", "mercado": "bcba", "cantidad": 1, "precio": 30},  # 80+30 > 100
    )
    assert not d.allow
    assert "diario" in d.reason.lower()
    store.close()


async def test_order_without_price_is_denied(tmp_path):
    """F7 (jury): si no se puede calcular el monto (falta precio), bloquear — no evadir límites."""
    called = False

    async def send(oid, summary):
        nonlocal called
        called = True

    gate, store, _ = _gate(tmp_path, send)
    d = await gate.evaluate(
        "mcp__iol__place_buy",
        {"simbolo": "SPY", "mercado": "bcba", "cantidad": 10},  # sin precio → monto 0
    )
    assert not d.allow
    assert not called  # ni siquiera molesta al usuario
    store.close()


async def test_unknown_write_tool_denied_by_default(tmp_path):
    """F8 (jury): una tool de orden no reconocida (drift) se bloquea por defecto."""
    async def send(oid, summary):
        raise AssertionError("no debería pedir confirmación para una tool desconocida")

    gate, store, _ = _gate(tmp_path, send)
    d = await gate.evaluate(
        "mcp__iol__place_short",  # no está en ORDER_TOOLS, pero matchea patrón de orden
        {"simbolo": "SPY", "mercado": "bcba", "cantidad": 1, "precio": 1},
    )
    assert not d.allow
    store.close()


async def test_approval_flow_allows(tmp_path):
    broker_ref = {}

    async def send(oid, summary):
        # simula que el usuario toca "Confirmar" apenas llega
        broker_ref["broker"].resolve(oid, True)

    settings = make_settings(tmp_path, order_confirmation_timeout_min=1)
    store = Store(settings.state_db_path)
    broker = ApprovalBroker()
    broker_ref["broker"] = broker
    gate = ConfirmationGate(settings, store, broker, send)

    d = await gate.evaluate(
        "mcp__iol__place_buy",
        {"simbolo": "SPY", "mercado": "bcba", "cantidad": 1, "precio": 100},
    )
    assert d.allow
    store.close()


async def test_timeout_denies(tmp_path):
    async def send(oid, summary):
        pass  # nadie confirma

    gate, store, _ = _gate(tmp_path, send, order_confirmation_timeout_min=0)
    d = await gate.evaluate(
        "mcp__iol__place_buy",
        {"simbolo": "SPY", "mercado": "bcba", "cantidad": 1, "precio": 100},
    )
    assert not d.allow
    assert "expir" in d.reason.lower()
    store.close()
