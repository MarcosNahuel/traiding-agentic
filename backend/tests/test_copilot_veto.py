"""Unit tests for the Claude veto co-pilot gate (app.services.copilot.veto_agent).

The SDK boundary (_run_sdk_veto) is always patched — CI never calls Claude live.
These tests pin the safety invariants: fail-open, disabled passthrough, BUY-only.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import so unittest.mock.patch can resolve "app.services.copilot.veto_agent.*"
# regardless of test execution order (3.13 patch does not auto-import submodules).
from app.services.copilot import veto_agent  # noqa: E402,F401


def _kwargs(**over):
    base = dict(
        symbol="ETHUSDT",
        trade_type="buy",
        price=3000.0,
        quantity=0.02,
        notional=60.0,
        reasoning="Entry[default]: RSI=42, ADX=25",
        proposal_id="prop-123",
        indicators_snapshot={"rsi_14": 42.0, "adx_14": 25.0},
        regime_snapshot={"regime": "ranging", "confidence": 70.0},
    )
    base.update(over)
    return base


def _settings(**over):
    s = MagicMock()
    s.copilot_enabled = True
    s.copilot_timeout_s = 5.0
    s.copilot_max_turns = 8
    s.copilot_model = ""
    s.claude_code_oauth_token = "sk-ant-oat01-test"
    for k, v in over.items():
        setattr(s, k, v)
    return s


@pytest.mark.asyncio
async def test_disabled_is_passthrough_and_never_calls_sdk():
    """COPILOT_ENABLED=false → skipped verdict, SDK never invoked."""
    sdk = AsyncMock(return_value={"approve": True})
    with patch("app.services.copilot.veto_agent.settings", _settings(copilot_enabled=False)), \
         patch("app.services.copilot.veto_agent._run_sdk_veto", sdk):
        from app.services.copilot.veto_agent import veto_gate
        verdict = await veto_gate(**_kwargs())

    assert verdict.veto is False
    assert verdict.skipped is True
    sdk.assert_not_called()


@pytest.mark.asyncio
async def test_non_buy_is_never_gated():
    """A sell never reaches the SDK — exits stay deterministic."""
    sdk = AsyncMock(return_value={"approve": False})
    with patch("app.services.copilot.veto_agent.settings", _settings()), \
         patch("app.services.copilot.veto_agent._run_sdk_veto", sdk):
        from app.services.copilot.veto_agent import veto_gate
        verdict = await veto_gate(**_kwargs(trade_type="sell"))

    assert verdict.veto is False
    assert verdict.skipped is True
    sdk.assert_not_called()


@pytest.mark.asyncio
async def test_approve_verdict_lets_trade_through():
    sdk = AsyncMock(return_value={"approve": True, "confidence": 0.8, "reason": "clean trend"})
    with patch("app.services.copilot.veto_agent.settings", _settings()), \
         patch("app.services.copilot.veto_agent._run_sdk_veto", sdk):
        from app.services.copilot.veto_agent import veto_gate
        verdict = await veto_gate(**_kwargs())

    assert verdict.veto is False
    assert verdict.failed_open is False
    assert verdict.reason == "clean trend"


@pytest.mark.asyncio
async def test_veto_verdict_blocks_trade():
    sdk = AsyncMock(return_value={"approve": False, "confidence": 0.9, "reason": "chop, no breakout"})
    with patch("app.services.copilot.veto_agent.settings", _settings()), \
         patch("app.services.copilot.veto_agent._run_sdk_veto", sdk):
        from app.services.copilot.veto_agent import veto_gate
        verdict = await veto_gate(**_kwargs())

    assert verdict.veto is True
    assert verdict.failed_open is False
    assert "chop" in verdict.reason


@pytest.mark.asyncio
async def test_timeout_fails_open():
    """SDK slower than timeout → fail-open (veto=False, failed_open=True)."""
    async def slow(**_):
        await asyncio.sleep(1.0)
        return {"approve": False}

    with patch("app.services.copilot.veto_agent.settings", _settings(copilot_timeout_s=0.05)), \
         patch("app.services.copilot.veto_agent._run_sdk_veto", slow):
        from app.services.copilot.veto_agent import veto_gate
        verdict = await veto_gate(**_kwargs())

    assert verdict.veto is False
    assert verdict.failed_open is True


@pytest.mark.asyncio
async def test_sdk_exception_fails_open():
    sdk = AsyncMock(side_effect=RuntimeError("CLI not found"))
    with patch("app.services.copilot.veto_agent.settings", _settings()), \
         patch("app.services.copilot.veto_agent._run_sdk_veto", sdk):
        from app.services.copilot.veto_agent import veto_gate
        verdict = await veto_gate(**_kwargs())

    assert verdict.veto is False
    assert verdict.failed_open is True
    assert "RuntimeError" in verdict.reason


@pytest.mark.asyncio
async def test_no_verdict_emitted_fails_open():
    """Agent finished without calling submit_verdict → fail-open, never block on ambiguity."""
    sdk = AsyncMock(return_value={"tool_calls": ["search_kb"]})  # no 'approve' key
    with patch("app.services.copilot.veto_agent.settings", _settings()), \
         patch("app.services.copilot.veto_agent._run_sdk_veto", sdk):
        from app.services.copilot.veto_agent import veto_gate
        verdict = await veto_gate(**_kwargs())

    assert verdict.veto is False
    assert verdict.failed_open is True


# ── record_veto: status flip + counterfactual ledger ──

def test_record_veto_sets_status_vetoed_and_logs_event():
    from app.services.copilot.veto_agent import VetoVerdict, record_veto

    supabase = MagicMock()
    verdict = VetoVerdict(veto=True, confidence=0.9, reason="ranging sin breakout")
    record_veto(
        supabase,
        proposal_id="p1",
        symbol="ETHUSDT",
        price=3000.0,
        quantity=0.02,
        notional=60.0,
        reasoning="Entry[default]: RSI=42",
        verdict=verdict,
        indicators_snapshot={"rsi_14": 42.0},
        regime_snapshot={"regime": "ranging", "confidence": 70.0},
    )

    supabase.table.assert_any_call("trade_proposals")
    supabase.table.assert_any_call("risk_events")

    update_payload = supabase.table.return_value.update.call_args.args[0]
    assert update_payload["status"] == "vetoed"
    assert "ranging sin breakout" in update_payload["reasoning"]

    event = supabase.table.return_value.insert.call_args.args[0]
    assert event["event_type"] == "copilot_veto"
    # Full candidate context persisted for strategy_replay reconstruction
    assert event["details"]["symbol"] == "ETHUSDT"
    assert event["details"]["price"] == 3000.0
    assert event["details"]["verdict"]["reason"] == "ranging sin breakout"
    assert event["details"]["indicators"]["rsi_14"] == 42.0


def test_record_veto_falls_back_to_rejected_when_vetoed_status_rejected():
    """If the DB check constraint rejects 'vetoed', fall back to 'rejected' (don't crash)."""
    from app.services.copilot.veto_agent import VetoVerdict, record_veto

    supabase = MagicMock()
    seen_statuses = []

    def update_side(payload):
        seen_statuses.append(payload.get("status"))
        chain = MagicMock()
        if payload.get("status") == "vetoed":
            chain.eq.return_value.execute.side_effect = Exception("violates check constraint")
        else:
            chain.eq.return_value.execute.return_value = MagicMock(data=[{"id": "p1"}])
        return chain

    supabase.table.return_value.update.side_effect = update_side

    verdict = VetoVerdict(veto=True, confidence=0.8, reason="loss streak")
    record_veto(
        supabase, proposal_id="p1", symbol="ETHUSDT", price=3000.0, quantity=0.02,
        notional=60.0, reasoning="Entry", verdict=verdict,
    )

    assert seen_statuses == ["vetoed", "rejected"]
