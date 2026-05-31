"""Tests for the strategist runner: parse submit_decision + fail-safe (degraded run).

The SDK boundary (_run_sdk) is always patched — CI never calls Claude live.
"""
from unittest.mock import AsyncMock, patch

import pytest

# Import so patch can resolve the module attribute regardless of test order.
from app.services.strategist import agent  # noqa: E402,F401


@pytest.mark.asyncio
async def test_parses_tweak_decision_with_config():
    raw = {
        "decision": "TWEAK_PARAMS",
        "confidence": 0.75,
        "summary": "tighten ADX in chop",
        "evidence": "- ETH WR 78%/9\n- funding negative 36h\n- F&G 48",
        "proposed_config_json": '{"buy_adx_min": 25}',
        "risks": "small sample",
    }
    with patch("app.services.strategist.agent._run_sdk", AsyncMock(return_value=raw)):
        d = await agent.run_strategist()

    assert d.decision == "TWEAK_PARAMS"
    assert d.confidence == 0.75
    assert d.proposed_config == {"buy_adx_min": 25}
    assert len(d.evidence) == 3


@pytest.mark.asyncio
async def test_run_fails_safe_on_sdk_error():
    with patch("app.services.strategist.agent._run_sdk", AsyncMock(side_effect=RuntimeError("CLI boom"))):
        d = await agent.run_strategist()

    assert d.decision == "KEEP_AS_IS"
    assert d.confidence == 0.0
    assert "DEGRADED_RUN" in d.data_quality
    assert "CLI boom" in d.data_quality


@pytest.mark.asyncio
async def test_no_decision_emitted_degrades():
    with patch("app.services.strategist.agent._run_sdk", AsyncMock(return_value={"tool_calls": []})):
        d = await agent.run_strategist()
    assert d.decision == "KEEP_AS_IS"
    assert "DEGRADED_RUN" in d.data_quality


@pytest.mark.asyncio
async def test_invalid_decision_type_degrades():
    with patch("app.services.strategist.agent._run_sdk", AsyncMock(return_value={"decision": "GO_MAINNET"})):
        d = await agent.run_strategist()
    assert d.decision == "KEEP_AS_IS"


@pytest.mark.asyncio
async def test_tweak_without_config_json_keeps_none():
    raw = {"decision": "TWEAK_PARAMS", "confidence": 0.6, "summary": "x", "evidence": "a\nb\nc",
           "proposed_config_json": ""}
    with patch("app.services.strategist.agent._run_sdk", AsyncMock(return_value=raw)):
        d = await agent.run_strategist()
    assert d.decision == "TWEAK_PARAMS"
    assert d.proposed_config is None
