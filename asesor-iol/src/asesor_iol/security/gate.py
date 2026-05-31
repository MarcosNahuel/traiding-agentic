"""Gate de confirmación: ninguna orden toca el mercado sin tu OK explícito.

Mecanismo: el callback `can_use_tool` del Claude Agent SDK intercepta cada tool
call ANTES de ejecutarla. Para tools de orden:
  1) valida límites duros (monto, tope diario, símbolos) -> deniega si excede;
  2) crea una orden pendiente, la manda a Telegram con botones;
  3) espera tu confirmación (con timeout) -> permite o bloquea.

Principio rector: ante la duda, NO opera. El peor caso es "no pasa nada".

NOTA: la forma exacta del valor de retorno de `can_use_tool` puede variar según
la versión de `claude-agent-sdk`. Acá se devuelven los tipos del SDK si están
disponibles, con fallback a dict. Verificar contra la versión instalada.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable

from ..config import Settings
from ..state.store import Store

# Tools de escritura que SIEMPRE pasan por el gate.
ORDER_TOOLS = {
    "mcp__iol__place_buy",
    "mcp__iol__place_sell",
    "mcp__iol__cancel_order",
}

# F8 (jury): patrones de tools de orden/escritura del server IOL. Cualquier tool que
# matchee y NO esté en ORDER_TOOLS se bloquea por defecto (deny-by-default contra drift:
# si mañana se agrega una tool de escritura y se olvida sumarla a ORDER_TOOLS, no se ejecuta).
# Semántica de escritura/orden. Fail-safe: cualquier tool de IOL cuyo nombre
# sugiera operar cae en deny-by-default si no está explícitamente en ORDER_TOOLS.
_ORDER_PATTERNS = (
    "place_", "cancel", "_order", "order",
    "buy", "sell", "comprar", "vender", "operar", "ejecutar",
)

# Lecturas conocidas y seguras de IOL: jamás se confunden con órdenes aunque
# su nombre contenga subcadenas ambiguas en el futuro.
_READ_ALLOWLIST = {
    "mcp__iol__get_portfolio",
    "mcp__iol__get_account_state",
    "mcp__iol__get_metrics",
    "mcp__iol__get_quote",
    "mcp__iol__get_panel",
    "mcp__iol__get_options",
    "mcp__iol__get_historical",
}


def _is_order_tool(name: str) -> bool:
    if name in ORDER_TOOLS:
        return True
    if name in _READ_ALLOWLIST:
        return False
    low = name.lower()
    return low.startswith("mcp__iol__") and any(p in low for p in _ORDER_PATTERNS)

# Callback que el bot de Telegram inyecta para mostrar la confirmación.
SendConfirmation = Callable[[str, str], Awaitable[None]]


@dataclass
class _Decision:
    allow: bool
    reason: str


class ApprovalBroker:
    """Coordina la espera del gate con la respuesta de los botones de Telegram."""

    def __init__(self) -> None:
        self._events: dict[str, asyncio.Event] = {}
        self._results: dict[str, bool] = {}

    def register(self, order_id: str) -> asyncio.Event:
        ev = asyncio.Event()
        self._events[order_id] = ev
        return ev

    def resolve(self, order_id: str, approved: bool) -> bool:
        ev = self._events.get(order_id)
        if ev is None:
            return False
        self._results[order_id] = approved
        ev.set()
        return True

    def result(self, order_id: str) -> bool:
        return self._results.pop(order_id, False)

    def cleanup(self, order_id: str) -> None:
        self._events.pop(order_id, None)
        self._results.pop(order_id, None)


class ConfirmationGate:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        broker: ApprovalBroker,
        send_confirmation: SendConfirmation,
    ) -> None:
        self._s = settings
        self._store = store
        self._broker = broker
        self._send = send_confirmation

    async def evaluate(self, tool_name: str, tool_input: dict) -> _Decision:
        if not _is_order_tool(tool_name):
            return _Decision(True, "lectura/no-orden: permitida")
        if tool_name not in ORDER_TOOLS:
            # F8: tool de orden no reconocida (drift) → deny-by-default, sin molestar al usuario.
            self._store.audit("gate_denied_unknown_write", tool_name, tool_input, None)
            return _Decision(False, "Tool de orden no reconocida — bloqueada por seguridad.")

        symbol = str(tool_input.get("simbolo", "")).upper()
        amount = _extract_amount(tool_input)

        # 1) Límites duros — se rechazan ANTES de molestarte.
        hard = self._check_hard_limits(symbol, amount)
        if hard is not None:
            self._store.audit("gate_denied_limit", tool_name, tool_input, {"reason": hard})
            return _Decision(False, hard)

        # 2) Confirmación humana.
        order_id = uuid.uuid4().hex[:12]
        self._store.create_pending(order_id, self._s.telegram_allowed_chat_id, tool_input, amount)
        ev = self._broker.register(order_id)
        await self._send(order_id, _summary(tool_name, tool_input, amount))

        timeout = self._s.order_confirmation_timeout_min * 60
        try:
            await asyncio.wait_for(ev.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self._store.resolve_pending(order_id, "expired")
            self._broker.cleanup(order_id)
            self._store.audit("gate_expired", tool_name, tool_input, None)
            return _Decision(False, "La orden expiró sin confirmación. No se ejecutó.")

        approved = self._broker.result(order_id)
        self._broker.cleanup(order_id)
        if approved:
            self._store.resolve_pending(order_id, "executed")
            self._store.audit("gate_approved", tool_name, tool_input, {"order_id": order_id})
            return _Decision(True, "Confirmada por el usuario.")
        self._store.resolve_pending(order_id, "cancelled")
        self._store.audit("gate_cancelled", tool_name, tool_input, None)
        return _Decision(False, "El usuario canceló la orden.")

    def _check_hard_limits(self, symbol: str, amount: float) -> str | None:
        allowed = self._s.allowed_symbols_set
        if allowed and symbol not in allowed:
            return f"Símbolo {symbol} no está en la lista permitida. Bloqueado."
        if amount <= 0:
            # F7 (jury): sin monto confiable (falta precio/cantidad) no se pueden acotar los
            # límites de dinero — bloquear en vez de evadirlos silenciosamente.
            return "No se pudo determinar el monto de la orden (falta precio/cantidad). Bloqueada."
        if amount > self._s.max_order_amount:
            return (
                f"Monto {amount:.2f} excede el máximo por orden "
                f"({self._s.max_order_amount:.2f}). Bloqueado."
            )
        # F1 (jury): contar comprometido (pending+executed), no solo executed.
        if self._store.committed_amount_today() + amount > self._s.max_daily_amount:
            return (
                f"La orden superaría el tope diario "
                f"({self._s.max_daily_amount:.2f}). Bloqueada."
            )
        return None


def _extract_amount(tool_input: dict) -> float:
    """Monto aproximado de la orden = cantidad * precio (si están)."""
    try:
        return float(tool_input.get("cantidad", 0)) * float(tool_input.get("precio", 0))
    except (TypeError, ValueError):
        return 0.0


def _summary(tool_name: str, tool_input: dict, amount: float) -> str:
    accion = "COMPRAR" if "buy" in tool_name else "VENDER" if "sell" in tool_name else "CANCELAR"
    return (
        f"📋 ORDEN PENDIENTE\n"
        f"Acción: {accion}\n"
        f"Símbolo: {tool_input.get('simbolo', '?')} ({tool_input.get('mercado', '?')})\n"
        f"Cantidad: {tool_input.get('cantidad', '?')}  ·  Precio: {tool_input.get('precio', '?')}\n"
        f"Monto aprox: {amount:.2f}\n\n"
        f"¿Confirmás?"
    )
