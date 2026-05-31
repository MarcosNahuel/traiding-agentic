"""Integration test for the veto hook inside signal_generator._submit_proposal.

Proves the safety-critical glue: a veto blocks execute_proposal; an approve lets it
through; copilot disabled is a no-op. The SDK is never touched (veto_gate is patched).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import ValidationResult
from app.services.copilot.veto_agent import VetoVerdict


def _supabase():
    sb = MagicMock()
    insert_resp = MagicMock()
    insert_resp.data = [{"id": "prop-1"}]
    sb.table.return_value.insert.return_value.execute.return_value = insert_resp
    return sb


def _settings(copilot_enabled=True, trading_enabled=True):
    s = MagicMock()
    s.copilot_enabled = copilot_enabled
    s.trading_enabled = trading_enabled
    s.quant_buy_notional_usd = 60.0
    return s


def _approved():
    return ValidationResult(approved=True, auto_approved=True, risk_score=10.0, checks=[])


def _patches(settings_obj, veto_gate_mock, execute_mock, record_mock):
    return [
        patch("app.services.signal_generator.settings", settings_obj),
        patch("app.services.signal_generator._round_quantity", return_value=0.02),
        patch("app.config.get_symbol_notional", return_value=60.0),
        patch("app.services.quant_risk.validate_proposal_enhanced",
              AsyncMock(return_value=_approved())),
        patch("app.services.telegram_notifier.send_telegram", AsyncMock(return_value=True)),
        patch("app.services.executor.execute_proposal", execute_mock),
        patch("app.services.copilot.veto_agent.veto_gate", veto_gate_mock),
        patch("app.services.copilot.veto_agent.record_veto", record_mock),
    ]


async def _run(settings_obj, veto_gate_mock, execute_mock, record_mock, trade_type="buy"):
    from contextlib import ExitStack
    sb = _supabase()
    with ExitStack() as stack:
        for p in _patches(settings_obj, veto_gate_mock, execute_mock, record_mock):
            stack.enter_context(p)
        from app.services.signal_generator import _submit_proposal
        await _submit_proposal(sb, trade_type, "ETHUSDT", 3000.0, "Entry[default]: RSI=42")
    return sb


def _status_updates(sb):
    return [
        c.args[0].get("status")
        for c in sb.table.return_value.update.call_args_list
        if c.args and isinstance(c.args[0], dict) and "status" in c.args[0]
    ]


@pytest.mark.asyncio
async def test_veto_blocks_execution():
    veto_gate = AsyncMock(return_value=VetoVerdict(veto=True, reason="ranging chop"))
    execute = AsyncMock(return_value={"ok": True})
    record = MagicMock()
    await _run(_settings(copilot_enabled=True), veto_gate, execute, record)

    veto_gate.assert_awaited_once()
    execute.assert_not_awaited()       # the trade was blocked
    record.assert_called_once()        # and logged for replay


@pytest.mark.asyncio
async def test_approve_lets_execution_through():
    veto_gate = AsyncMock(return_value=VetoVerdict(veto=False, reason="clean"))
    execute = AsyncMock(return_value={"ok": True})
    record = MagicMock()
    await _run(_settings(copilot_enabled=True), veto_gate, execute, record)

    veto_gate.assert_awaited_once()
    execute.assert_awaited_once()
    record.assert_not_called()


@pytest.mark.asyncio
async def test_veto_leaves_proposal_validated_not_approved():
    """F3 (jury): un veto NUNCA debe dejar la propuesta en 'approved' — execute_all_approved
    (corre cada tick) la ejecutaría, anulando el veto si record_veto fallara."""
    sb = await _run(
        _settings(copilot_enabled=True),
        AsyncMock(return_value=VetoVerdict(veto=True, reason="chop")),
        AsyncMock(), MagicMock(),
    )
    statuses = _status_updates(sb)
    assert statuses, "expected status updates"
    assert statuses[-1] == "validated"
    assert statuses[-1] != "approved"


@pytest.mark.asyncio
async def test_approve_restores_approved_status():
    """Tras aprobar el veto, la propuesta vuelve a 'approved' para ejecutarse."""
    sb = await _run(
        _settings(copilot_enabled=True),
        AsyncMock(return_value=VetoVerdict(veto=False, reason="ok")),
        AsyncMock(), MagicMock(),
    )
    assert _status_updates(sb)[-1] == "approved"


@pytest.mark.asyncio
async def test_copilot_disabled_is_noop():
    veto_gate = AsyncMock(return_value=VetoVerdict(veto=True, reason="should not run"))
    execute = AsyncMock(return_value={"ok": True})
    record = MagicMock()
    await _run(_settings(copilot_enabled=False), veto_gate, execute, record)

    veto_gate.assert_not_awaited()     # gate never consulted
    execute.assert_awaited_once()      # behaves exactly like today
