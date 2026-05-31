"""Adaptadores entre la seguridad propia y el harness del Claude Agent SDK.

- `make_can_use_tool`: conecta el ConfirmationGate al callback de permisos del SDK.
- `make_audit_hook`: PostToolUse hook que loguea cada tool call (append-only).

NOTA: las firmas/retornos exactos dependen de la versión de `claude-agent-sdk`.
Se importan los tipos del SDK si existen, con fallback a dict. Verificar al correr.
"""
from __future__ import annotations

from typing import Any

from ..state.store import Store
from .gate import ConfirmationGate

try:  # los tipos del SDK pueden variar entre versiones
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny  # type: ignore
except Exception:  # pragma: no cover - fallback si la API difiere
    PermissionResultAllow = None  # type: ignore
    PermissionResultDeny = None  # type: ignore


def _allow() -> Any:
    if PermissionResultAllow is not None:
        return PermissionResultAllow()
    return {"behavior": "allow"}


def _deny(reason: str) -> Any:
    if PermissionResultDeny is not None:
        return PermissionResultDeny(message=reason)
    return {"behavior": "deny", "message": reason}


def make_can_use_tool(gate: ConfirmationGate):
    """Devuelve un callback `can_use_tool` para ClaudeAgentOptions."""

    async def can_use_tool(tool_name: str, tool_input: dict, context: Any = None) -> Any:
        decision = await gate.evaluate(tool_name, tool_input)
        return _allow() if decision.allow else _deny(decision.reason)

    return can_use_tool


def make_audit_hook(store: Store):
    """Devuelve un hook PostToolUse que loguea cada ejecución de tool."""

    async def audit_hook(input_data: dict, tool_use_id: str | None, context: Any = None) -> dict:
        store.audit(
            "post_tool_use",
            input_data.get("tool_name"),
            input_data.get("tool_input"),
            input_data.get("tool_response"),
        )
        return {}

    return audit_hook
