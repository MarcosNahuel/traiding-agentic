"""Orquestador: arma las opciones del SDK y procesa cada turno del usuario.

- Orquestador en modelo Opus (juicio + decisión).
- Subagentes datos/conocimiento con modelos baratos.
- Gate de confirmación via can_use_tool. Audit via PostToolUse.
- Mantiene continuidad de conversación con session_id (resume).
"""
from __future__ import annotations

from typing import Any

from claude_agent_sdk import (  # type: ignore
    ClaudeAgentOptions,
    HookMatcher,
    query,
)

from ..config import Settings
from ..iol.client import IOLClient
from ..security.gate import ApprovalBroker, ConfirmationGate, SendConfirmation
from ..security.hooks import make_audit_hook, make_can_use_tool
from ..state.store import Store
from . import prompts
from .definitions import build_agents
from .tools import build_iol_server

ALLOWED_TOOLS = [
    "mcp__iol__get_portfolio",
    "mcp__iol__get_account_state",
    "mcp__iol__get_metrics",
    "mcp__iol__get_quote",
    "mcp__iol__place_buy",
    "mcp__iol__place_sell",
    "WebSearch",
    "WebFetch",
    "Read",
    "Agent",
]


class Advisor:
    def __init__(
        self,
        settings: Settings,
        iol_client: IOLClient,
        store: Store,
        broker: ApprovalBroker,
        send_confirmation: SendConfirmation,
    ) -> None:
        self._s = settings
        self._store = store
        self._session_id: str | None = None

        gate = ConfirmationGate(settings, store, broker, send_confirmation)
        iol_server = build_iol_server(iol_client)

        self._options = ClaudeAgentOptions(
            system_prompt=prompts.ORCHESTRATOR,
            model=settings.model_orchestrator,
            mcp_servers={"iol": iol_server},
            allowed_tools=ALLOWED_TOOLS,
            agents=build_agents(settings),
            can_use_tool=make_can_use_tool(gate),
            hooks={"PostToolUse": [HookMatcher(matcher="*", hooks=[make_audit_hook(store)])]},
            setting_sources=[],  # headless: no cargar .claude/ del filesystem
        )

    async def ask(self, message: str) -> str:
        """Procesa un mensaje del usuario y devuelve la respuesta final."""
        options = self._options
        if self._session_id:
            options = _with_resume(self._options, self._session_id)

        final = ""
        async for msg in query(prompt=message, options=options):
            sid = _extract_session_id(msg)
            if sid:
                self._session_id = sid
            result = _extract_result(msg)
            if result is not None:
                final = result
        return final or "No pude generar una respuesta."


def _with_resume(options: ClaudeAgentOptions, session_id: str) -> ClaudeAgentOptions:
    try:
        import dataclasses

        return dataclasses.replace(options, resume=session_id)
    except Exception:  # pragma: no cover
        options.resume = session_id  # type: ignore[attr-defined]
        return options


def _extract_session_id(msg: Any) -> str | None:
    sid = getattr(msg, "session_id", None)
    if sid:
        return sid
    data = getattr(msg, "data", None)
    if isinstance(data, dict):
        return data.get("session_id")
    return None


def _extract_result(msg: Any) -> str | None:
    if getattr(msg, "result", None) is not None:
        return str(msg.result)
    return None
