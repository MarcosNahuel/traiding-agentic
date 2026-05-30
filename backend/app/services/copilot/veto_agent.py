"""Claude veto co-pilot gate — the testable orchestration layer.

veto_gate() owns all the safety logic (disabled passthrough, BUY-only, timeout,
fail-open) and is fully unit-testable by patching _run_sdk_veto. _run_sdk_veto is
the ONLY code that touches claude_agent_sdk, lazily imported so this module loads
(and tests run) without the SDK / Claude CLI.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ...config import settings

log = logging.getLogger(__name__)

_PROMPT_CACHE: str | None = None


class VetoVerdict(BaseModel):
    """Outcome of the gate. `veto=True` blocks execution; everything else lets it through."""
    veto: bool = False
    confidence: float = 0.0
    reason: str = ""
    skipped: bool = False        # disabled or non-buy → SDK never invoked
    failed_open: bool = False    # SDK error/timeout/no-verdict → defaulted to approve
    latency_ms: int = 0
    tool_calls: list[Any] = Field(default_factory=list)


async def veto_gate(
    *,
    symbol: str,
    trade_type: str,
    price: float,
    quantity: float,
    notional: float,
    reasoning: str,
    proposal_id: str,
    indicators_snapshot: dict | None = None,
    regime_snapshot: dict | None = None,
) -> VetoVerdict:
    """Second gate after the deterministic risk gate. Vetoes only BUY entries.

    Invariants:
      - disabled (COPILOT_ENABLED=false) or non-buy → skipped passthrough, SDK not called
      - any error/timeout/missing verdict → fail-open (veto=False), never block on failure
      - Claude can only make the decision MORE conservative; it cannot approve what
        the deterministic gate already rejected (that gate runs before this is called).
    """
    if not settings.copilot_enabled:
        return VetoVerdict(skipped=True, reason="copilot disabled")
    if (trade_type or "").lower() != "buy":
        return VetoVerdict(skipped=True, reason="non-buy not gated")

    start = time.monotonic()
    try:
        raw = await asyncio.wait_for(
            _run_sdk_veto(
                symbol=symbol,
                price=price,
                quantity=quantity,
                notional=notional,
                reasoning=reasoning,
                indicators_snapshot=indicators_snapshot or {},
                regime_snapshot=regime_snapshot or {},
            ),
            timeout=float(settings.copilot_timeout_s),
        )
    except asyncio.TimeoutError:
        ms = int((time.monotonic() - start) * 1000)
        log.warning("copilot veto timeout for %s (%dms) — failing open", symbol, ms)
        return VetoVerdict(veto=False, failed_open=True, reason="timeout", latency_ms=ms)
    except Exception as e:  # noqa: BLE001 — fail-open is the entire point of this gate
        ms = int((time.monotonic() - start) * 1000)
        log.warning("copilot veto error for %s: %s — failing open", symbol, e)
        return VetoVerdict(
            veto=False, failed_open=True, reason=f"{type(e).__name__}: {e}"[:300], latency_ms=ms
        )

    ms = int((time.monotonic() - start) * 1000)
    if not isinstance(raw, dict) or "approve" not in raw:
        tc = raw.get("tool_calls", []) if isinstance(raw, dict) else []
        log.warning("copilot veto emitted no verdict for %s — failing open", symbol)
        return VetoVerdict(
            veto=False, failed_open=True, reason="no verdict emitted", latency_ms=ms, tool_calls=tc
        )

    approve = bool(raw["approve"])
    verdict = VetoVerdict(
        veto=not approve,
        confidence=float(raw.get("confidence", 0.0) or 0.0),
        reason=str(raw.get("reason", "")),
        tool_calls=raw.get("tool_calls", []),
        latency_ms=ms,
    )
    log.info(
        "copilot veto %s %s (conf=%.2f, %dms): %s",
        "VETO" if verdict.veto else "approve",
        symbol,
        verdict.confidence,
        ms,
        verdict.reason[:160],
    )
    return verdict


def record_veto(
    supabase: Any,
    *,
    proposal_id: str,
    symbol: str,
    price: float,
    quantity: float,
    notional: float,
    reasoning: str,
    verdict: VetoVerdict,
    indicators_snapshot: dict | None = None,
    regime_snapshot: dict | None = None,
) -> None:
    """Persist a veto: flip proposal status + log the full candidate context.

    Fail-safe — never raises into the trading loop. The risk_events row carries the
    full candidate so strategy_replay can reconstruct the counterfactual PnL later
    (this is how we measure the veto's edge even in enforce mode).
    Falls back to status='rejected' if the DB check constraint disallows 'vetoed'.
    """
    now = datetime.now(timezone.utc).isoformat()
    new_reasoning = (reasoning or "") + f"\n[COPILOT VETO conf={verdict.confidence:.2f}] {verdict.reason}"

    for status in ("vetoed", "rejected"):
        try:
            supabase.table("trade_proposals").update(
                {"status": status, "reasoning": new_reasoning, "updated_at": now}
            ).eq("id", proposal_id).execute()
            break
        except Exception as e:  # noqa: BLE001
            if status == "vetoed":
                log.warning("status 'vetoed' rejected by DB (%s) — falling back to 'rejected'", e)
                continue
            log.error("failed to record veto status for %s: %s", proposal_id, e)

    try:
        supabase.table("risk_events").insert(
            {
                "event_type": "copilot_veto",
                "severity": "info",
                "message": f"COPILOT VETO {symbol} @ ${price} — {verdict.reason}"[:500],
                "details": {
                    "symbol": symbol,
                    "price": price,
                    "quantity": quantity,
                    "notional": notional,
                    "reasoning": reasoning,
                    "indicators": indicators_snapshot or {},
                    "regime": regime_snapshot or {},
                    "verdict": {
                        "confidence": verdict.confidence,
                        "reason": verdict.reason,
                        "latency_ms": verdict.latency_ms,
                        "tool_calls": verdict.tool_calls,
                    },
                },
                "proposal_id": proposal_id,
            }
        ).execute()
    except Exception as e:  # noqa: BLE001
        log.warning("failed to log copilot_veto risk_event for %s: %s", proposal_id, e)


def _load_veto_prompt() -> str:
    global _PROMPT_CACHE
    if _PROMPT_CACHE is None:
        path = Path(__file__).parent / "prompts" / "veto.md"
        _PROMPT_CACHE = path.read_text(encoding="utf-8")
    return _PROMPT_CACHE


def _build_user_prompt(
    symbol: str,
    price: float,
    quantity: float,
    notional: float,
    reasoning: str,
    indicators_snapshot: dict,
    regime_snapshot: dict,
) -> str:
    return (
        "Evaluá esta entrada BUY que el motor cuant YA aprobó. Decidí si ejecutarla o vetarla.\n\n"
        f"Símbolo: {symbol}\n"
        f"Precio: {price}\n"
        f"Cantidad: {quantity}  (notional ${notional:.2f})\n"
        f"Razonamiento del motor: {reasoning}\n"
        f"Indicadores: {indicators_snapshot}\n"
        f"Régimen detectado: {regime_snapshot}\n\n"
        "Consultá el KB (search_kb/read_kb) y los trades recientes (get_recent_trades) si lo "
        "necesitás. Default a aprobar. Terminá SIEMPRE llamando submit_verdict."
    )


async def _run_sdk_veto(
    *,
    symbol: str,
    price: float,
    quantity: float,
    notional: float,
    reasoning: str,
    indicators_snapshot: dict,
    regime_snapshot: dict,
) -> dict:
    """The only SDK-touching code. Returns {"approve", "confidence", "reason", "tool_calls"}.

    If the agent never calls submit_verdict, returns a dict WITHOUT "approve" so the
    caller fails open.
    """
    from claude_agent_sdk import (  # lazy import — keeps module + tests SDK-free
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        ToolUseBlock,
    )

    from .veto_tools import ALLOWED_TOOL_NAMES, create_copilot_server

    options_kwargs: dict[str, Any] = {
        "system_prompt": _load_veto_prompt(),
        "mcp_servers": {"copilot": create_copilot_server()},
        "allowed_tools": ALLOWED_TOOL_NAMES,
        "permission_mode": "bypassPermissions",
        "max_turns": int(settings.copilot_max_turns),
    }
    if settings.copilot_model:
        options_kwargs["model"] = settings.copilot_model
    options = ClaudeAgentOptions(**options_kwargs)

    user_prompt = _build_user_prompt(
        symbol, price, quantity, notional, reasoning, indicators_snapshot, regime_snapshot
    )

    verdict: dict | None = None
    tool_calls: list[str] = []
    async with ClaudeSDKClient(options=options) as client:
        await client.query(user_prompt)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        tool_calls.append(block.name)
                        if block.name.endswith("submit_verdict"):
                            inp = block.input if isinstance(block.input, dict) else {}
                            verdict = {
                                "approve": bool(inp.get("approve", True)),  # bias to approve
                                "confidence": float(inp.get("confidence", 0.0) or 0.0),
                                "reason": str(inp.get("reason", "")),
                            }

    if verdict is None:
        return {"tool_calls": tool_calls}
    verdict["tool_calls"] = tool_calls
    return verdict
