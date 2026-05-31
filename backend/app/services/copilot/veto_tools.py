"""@tool wrappers + MCP server factory for the veto co-pilot.

Thin layer over the SDK-free impls in kb_tools.py. This module imports
claude_agent_sdk, so it is only imported lazily from veto_agent._run_sdk_veto
(never at the top of veto_agent, to keep that module + its tests SDK-free).
"""
from __future__ import annotations

import json
from pathlib import Path

from claude_agent_sdk import create_sdk_mcp_server, tool

from ...config import settings
from . import kb_tools
from .kb_tools import get_recent_trades_impl, read_kb_impl, search_kb_impl


def _kb_root() -> Path:
    """KB location: COPILOT_KB_DIR if set (deploy bind-mount), else repo-relative default."""
    return Path(settings.copilot_kb_dir) if settings.copilot_kb_dir else kb_tools.KB_ROOT


def _text(payload: dict, limit: int = 6000) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, default=str)[:limit]}]}


@tool(
    "search_kb",
    "Busca en el Knowledge Base de estrategias (docs/knowledge-base). Devuelve paths + snippets. "
    "Usalo para encontrar las reglas del régimen actual, la decision-matrix o la estrategia activa.",
    {"query": str},
)
async def search_kb(args: dict) -> dict:
    return _text(search_kb_impl(args.get("query", ""), kb_root=_kb_root()))


@tool(
    "read_kb",
    "Lee un documento del KB por su path relativo (ej. 'decision-matrix.md', "
    "'market-regimes/ranging-high-vol.md', 'strategies/01-trend-momentum.md').",
    {"path": str},
)
async def read_kb(args: dict) -> dict:
    return _text(read_kb_impl(args.get("path", ""), kb_root=_kb_root()), limit=8000)


@tool(
    "get_recent_trades",
    "Devuelve los últimos N cierres del símbolo (PnL, fecha). Usalo para detectar rachas de "
    "pérdidas recientes que justifiquen vetar una nueva entrada.",
    {"symbol": str, "n": int},
)
async def get_recent_trades(args: dict) -> dict:
    from ...db import get_supabase

    n = int(args.get("n", 5) or 5)
    return _text(get_recent_trades_impl(args.get("symbol", ""), n, supabase=get_supabase()))


@tool(
    "submit_verdict",
    "Emití el veredicto final del gate. approve=true deja ejecutar el trade, approve=false lo veta. "
    "Default a approve=true salvo señal clara de trampa (chop sin breakout, racha de pérdidas, "
    "contradicción con el KB).",
    {"approve": bool, "confidence": float, "reason": str},
)
async def submit_verdict(args: dict) -> dict:
    # The verdict is captured by the caller from this ToolUseBlock's input.
    return {"content": [{"type": "text", "text": "verdict recorded"}]}


def create_copilot_server():
    """In-process MCP server with the 4 co-pilot tools."""
    return create_sdk_mcp_server(
        name="copilot",
        version="0.1.0",
        tools=[search_kb, read_kb, get_recent_trades, submit_verdict],
    )


ALLOWED_TOOL_NAMES = [
    "mcp__copilot__search_kb",
    "mcp__copilot__read_kb",
    "mcp__copilot__get_recent_trades",
    "mcp__copilot__submit_verdict",
]
