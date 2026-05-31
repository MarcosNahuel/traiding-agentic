"""Claude Agent SDK @tool wrappers for the strategist fleet.

Reuses the EXISTING data tools (services/daily_analyst/tools.py — already battle-tested)
via LangChain .ainvoke(), plus the copilot KB reader. No data-fetch logic is duplicated.
(When daily_analyst is decommissioned, inline these few wrappers.)

Imports claude_agent_sdk → only loaded lazily from agent._run_sdk (keeps agent.py SDK-free).
"""
from __future__ import annotations

import json
from pathlib import Path

from claude_agent_sdk import create_sdk_mcp_server, tool

from ...config import settings
from ..copilot import kb_tools
from ..daily_analyst import tools as da


def _text(payload, limit: int = 7000) -> dict:
    s = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, default=str)
    return {"content": [{"type": "text", "text": s[:limit]}]}


def _kb_root() -> Path:
    return Path(settings.copilot_kb_dir) if settings.copilot_kb_dir else kb_tools.KB_ROOT


# ── DATA tools (for the data-analyst subagent) ──

@tool("get_recent_trades", "Trades cerrados recientes de un símbolo (PnL, win-rate, holding).", {"symbol": str, "days": int})
async def get_recent_trades(args: dict) -> dict:
    return _text(await da.get_recent_trades.ainvoke({"symbol": args.get("symbol", ""), "days": int(args.get("days", 7) or 7)}))


@tool("get_portfolio_state", "Estado del portfolio: balance USDT, posiciones abiertas, PnL diario, drawdown.", {})
async def get_portfolio_state(args: dict) -> dict:
    return _text(await da.get_portfolio_state.ainvoke({}))


@tool("get_performance_metrics", "Métricas rolling: Sharpe, Sortino, win-rate, profit factor, drawdown, Kelly.", {})
async def get_performance_metrics(args: dict) -> dict:
    return _text(await da.get_performance_metrics.ainvoke({}))


@tool("get_quant_snapshot", "Análisis quant completo de un símbolo: indicadores, régimen, S/R, sizing.", {"symbol": str})
async def get_quant_snapshot(args: dict) -> dict:
    return _text(await da.get_quant_snapshot.ainvoke({"symbol": args.get("symbol", "")}))


@tool("get_ml_review", "Performance del modelo ML: hit-rate, Sharpe, recomendación enable/disable.", {})
async def get_ml_review(args: dict) -> dict:
    return _text(await da.get_ml_review.ainvoke({}))


# ── KNOWLEDGE tools (for the knowledge subagent) ──

@tool("get_fear_greed_index", "Crypto Fear & Greed Index actual (0-100) + clasificación.", {})
async def get_fear_greed_index(args: dict) -> dict:
    return _text(await da.get_fear_greed_index.ainvoke({}))


@tool("search_market_news", "Busca noticias cripto recientes (RSS cointelegraph/coindesk).", {"query": str})
async def search_market_news(args: dict) -> dict:
    return _text(await da.search_market_news.ainvoke({"query": args.get("query", "")}))


@tool("get_daily_research", "Research diario: news + estrategias conocidas + fuentes + docs disponibles.", {})
async def get_daily_research(args: dict) -> dict:
    return _text(await da.get_daily_research.ainvoke({}))


@tool("search_kb", "Busca en el Knowledge Base de estrategias (decision-matrix, regímenes, estrategia activa).", {"query": str})
async def search_kb(args: dict) -> dict:
    return _text(kb_tools.search_kb_impl(args.get("query", ""), kb_root=_kb_root()))


@tool("read_kb", "Lee un doc del KB por path relativo (ej. 'decision-matrix.md').", {"path": str})
async def read_kb(args: dict) -> dict:
    return _text(kb_tools.read_kb_impl(args.get("path", ""), kb_root=_kb_root()))


# ── DECISION sink (for the decision agent) ──

@tool(
    "submit_decision",
    "Emití la decisión final del día. decision ∈ {KEEP_AS_IS, TWEAK_PARAMS, "
    "PROPOSE_STRATEGY_CHANGE, RECOMMEND_PAUSE}. proposed_config_json: SOLO para TWEAK_PARAMS, "
    "un objeto JSON con los parámetros a cambiar (ej. {\"buy_adx_min\": 25}); '' si no aplica. "
    "evidence: una línea por dato citado (mínimo 3 para cambios).",
    {
        "decision": str, "confidence": float, "summary": str, "evidence": str,
        "proposed_config_json": str, "risks": str, "data_quality": str,
        "performance_review": str, "macro_context": str,
    },
)
async def submit_decision(args: dict) -> dict:
    return {"content": [{"type": "text", "text": "decision recorded"}]}


# Tool name groups (for per-subagent allowlists)
DATA_TOOLS = [
    "mcp__strategist__get_recent_trades", "mcp__strategist__get_portfolio_state",
    "mcp__strategist__get_performance_metrics", "mcp__strategist__get_quant_snapshot",
    "mcp__strategist__get_ml_review",
]
KNOWLEDGE_TOOLS = [
    "mcp__strategist__get_fear_greed_index", "mcp__strategist__search_market_news",
    "mcp__strategist__get_daily_research", "mcp__strategist__search_kb",
    "mcp__strategist__read_kb", "WebSearch",
]
DECISION_TOOLS = ["mcp__strategist__submit_decision"]
ALL_TOOL_NAMES = DATA_TOOLS + KNOWLEDGE_TOOLS + DECISION_TOOLS


def create_strategist_server():
    """In-process MCP server with all strategist tools."""
    return create_sdk_mcp_server(
        name="strategist",
        version="0.1.0",
        tools=[
            get_recent_trades, get_portfolio_state, get_performance_metrics,
            get_quant_snapshot, get_ml_review, get_fear_greed_index,
            search_market_news, get_daily_research, search_kb, read_kb, submit_decision,
        ],
    )
