"""Strategist fleet runner — multi-model subagents (data + knowledge) → decision (Opus/Sonnet).

run_strategist() owns the fail-safe + parse logic and is unit-testable by patching _run_sdk.
_run_sdk is the only claude_agent_sdk-touching code (lazy import), so this module + its tests
load without the SDK / CLI. Mirrors the proven services/copilot/veto_agent.py pattern.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

from ...config import settings
from ..daily_analyst.models import PARAM_BOUNDS
from .schemas import StrategistDecision

log = logging.getLogger(__name__)

_PROMPT_CACHE: dict[str, str] = {}
_DEFAULT_DATA_MODEL = "claude-opus-4-8"  # data-analyst en Opus (low-effort) por pedido
_DEFAULT_KNOWLEDGE_MODEL = "claude-sonnet-4-6"
_VALID = {"KEEP_AS_IS", "TWEAK_PARAMS", "PROPOSE_STRATEGY_CHANGE", "RECOMMEND_PAUSE"}


async def run_strategist() -> StrategistDecision:
    """Run the daily strategist fleet. Always returns a StrategistDecision (degraded on failure)."""
    start = time.monotonic()
    try:
        raw = await asyncio.wait_for(_run_sdk(), timeout=float(settings.strategist_timeout_s))
    except asyncio.TimeoutError:
        return _degraded("timeout")
    except Exception as e:  # noqa: BLE001 — a failed run must never crash the daily job
        log.exception("strategist run failed")
        return _degraded(f"{type(e).__name__}: {e}"[:300])

    decision = _parse_decision(raw)
    took = int((time.monotonic() - start) * 1000)
    if decision is None:
        log.warning("strategist emitted no valid decision (%dms)", took)
        return _degraded("no valid submit_decision emitted")
    log.info("strategist decision=%s confidence=%.2f (%dms)", decision.decision, decision.confidence, took)
    return decision


def _degraded(reason: str) -> StrategistDecision:
    return StrategistDecision(
        decision="KEEP_AS_IS",
        confidence=0.0,
        summary="Run degradado — el agente no produjo una decisión válida; se mantiene la config actual.",
        evidence=[],
        data_quality=f"DEGRADED_RUN: {reason}",
    )


def _parse_decision(raw: Any) -> Optional[StrategistDecision]:
    if not isinstance(raw, dict) or raw.get("decision") not in _VALID:
        return None
    dec = raw["decision"]
    evidence = [ln.strip("-*• \t").strip() for ln in str(raw.get("evidence", "")).splitlines() if ln.strip()]
    proposed = None
    pcj = str(raw.get("proposed_config_json", "") or "").strip()
    if dec == "TWEAK_PARAMS" and pcj:
        try:
            parsed = json.loads(pcj)
            if isinstance(parsed, dict):
                proposed = parsed
        except Exception:  # noqa: BLE001
            proposed = None
    try:
        return StrategistDecision(
            decision=dec,
            confidence=float(raw.get("confidence", 0.5) or 0.5),
            summary=str(raw.get("summary", "")),
            evidence=evidence,
            proposed_config=proposed,
            risks=str(raw.get("risks", "")),
            data_quality=str(raw.get("data_quality", "")),
            performance_review=str(raw.get("performance_review", "")),
            macro_context=str(raw.get("macro_context", "")),
        )
    except Exception:  # noqa: BLE001
        return None


def _load(name: str) -> str:
    if name not in _PROMPT_CACHE:
        _PROMPT_CACHE[name] = (Path(__file__).parent / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    return _PROMPT_CACHE[name]


def _bounds_text() -> str:
    return "\n".join(f"- `{k}`: [{lo}, {hi}]" for k, (lo, hi) in PARAM_BOUNDS.items())


def _decision_prompt() -> str:
    return _load("decision").replace("{BOUNDS}", _bounds_text())


async def _run_sdk() -> dict:
    """The only claude_agent_sdk-touching code. Returns the submit_decision input dict
    (or a dict without 'decision' if the agent never submitted → caller degrades)."""
    from claude_agent_sdk import (  # lazy import — keeps module + tests SDK-free
        AgentDefinition,
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        ToolUseBlock,
    )

    from .tools import ALL_TOOL_NAMES, DATA_TOOLS, KNOWLEDGE_TOOLS, create_strategist_server

    if settings.claude_code_oauth_token and not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = settings.claude_code_oauth_token

    agents = {
        "data-analyst": AgentDefinition(
            description="Audita datos cuantitativos del bot: trades, portfolio, performance, quant, ML.",
            prompt=_load("data_agent"),
            tools=DATA_TOOLS,
            model=settings.strategist_data_model or _DEFAULT_DATA_MODEL,
            effort=settings.strategist_data_effort or "low",
        ),
        "knowledge": AgentDefinition(
            description="Trae contexto macro/económico (Fear&Greed, news, web) y reglas del KB.",
            prompt=_load("knowledge_agent"),
            tools=KNOWLEDGE_TOOLS,
            model=settings.strategist_knowledge_model or _DEFAULT_KNOWLEDGE_MODEL,
        ),
    }

    options_kwargs: dict[str, Any] = {
        "system_prompt": _decision_prompt(),
        "mcp_servers": {"strategist": create_strategist_server()},
        "allowed_tools": [*ALL_TOOL_NAMES, "Task"],  # main agent can delegate OR work directly
        "agents": agents,
        "permission_mode": "bypassPermissions",
        "max_turns": int(settings.strategist_max_turns),
    }
    if settings.strategist_max_budget_usd and settings.strategist_max_budget_usd > 0:
        options_kwargs["max_budget_usd"] = float(settings.strategist_max_budget_usd)
    if settings.strategist_decision_model:
        options_kwargs["model"] = settings.strategist_decision_model
    options = ClaudeAgentOptions(**options_kwargs)

    user_prompt = (
        "Ejecutá tu evaluación diaria AHORA. Auditá los trades de ayer (delegá al data-analyst), "
        "investigá el contexto macro y las reglas del KB (delegá al knowledge), sintetizá y decidí. "
        "Terminá SIEMPRE llamando submit_decision."
    )

    result: dict | None = None
    tool_calls: list[str] = []
    async with ClaudeSDKClient(options=options) as client:
        await client.query(user_prompt)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        tool_calls.append(block.name)
                        if block.name.endswith("submit_decision"):
                            result = dict(block.input) if isinstance(block.input, dict) else {}

    if result is None:
        return {"tool_calls": tool_calls}
    result["tool_calls"] = tool_calls
    return result
