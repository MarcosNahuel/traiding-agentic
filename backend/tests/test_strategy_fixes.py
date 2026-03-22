"""Tests para los 6 fixes de estrategia (Mar 2026).

Bug 1: Sell spam — _execute_sl_tp debe prevenir sells duplicados via atomic claim
Bug 2: SOL/XRP fuera de quant_symbols (config)
Bug 3: ML signal_generator open_count cuenta posiciones totales
Fix 4: Trailing activation 40% → 65%
Fix 5: Cooldown 1h → 3h
Fix 6: ADX min 15 → 20
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock, call
from datetime import datetime, timezone


# ── Bug 1: Sell spam race condition ──

def _make_sl_tp_supabase(claim_succeeds=True):
    """Mock supabase for _execute_sl_tp with atomic position claim."""
    sb = MagicMock()

    # We need fine-grained control over different table calls.
    # The fix will do:
    #   1. supabase.table("positions").update({status:closing}).eq(id).eq(status,open).execute()
    #   2. supabase.table("trade_proposals").insert(...).execute()
    #   3. supabase.table("risk_events").insert(...).execute()

    claim_resp = MagicMock()
    claim_resp.data = [{"id": "pos-1"}] if claim_succeeds else []

    insert_resp = MagicMock()
    insert_resp.data = [{"id": "sell-proposal-1"}]

    # Build chain for atomic claim (update.eq.eq.execute)
    update_chain = MagicMock()
    update_chain.eq.return_value.eq.return_value.execute.return_value = claim_resp

    # Default table mock
    table_mock = MagicMock()
    table_mock.update.return_value = update_chain
    table_mock.insert.return_value.execute.return_value = insert_resp

    sb.table.return_value = table_mock
    return sb


@pytest.mark.asyncio
async def test_sl_tp_prevents_duplicate_sell():
    """When position is already being closed (atomic claim fails), skip sell."""
    sb = _make_sl_tp_supabase(claim_succeeds=False)
    position = {
        "id": "pos-1",
        "symbol": "BNBUSDT",
        "entry_price": "630.0",
        "current_quantity": "0.095",
        "status": "open",
    }

    with patch("app.services.trading_loop.round_quantity", return_value=0.095), \
         patch("app.services.executor.execute_proposal", new_callable=AsyncMock):
        from app.services.trading_loop import _execute_sl_tp
        await _execute_sl_tp(sb, position, 628.0, "stop_loss")

    # Should NOT have inserted a sell proposal
    sb.table.return_value.insert.assert_not_called()


@pytest.mark.asyncio
async def test_sl_tp_proceeds_when_claim_succeeds():
    """When atomic claim succeeds, _execute_sl_tp should create and execute sell."""
    sb = _make_sl_tp_supabase(claim_succeeds=True)
    position = {
        "id": "pos-1",
        "symbol": "BNBUSDT",
        "entry_price": "630.0",
        "current_quantity": "0.095",
        "status": "open",
    }

    with patch("app.services.trading_loop.round_quantity", return_value=0.095), \
         patch("app.services.executor.execute_proposal", new_callable=AsyncMock) as mock_exec:
        from app.services.trading_loop import _execute_sl_tp
        await _execute_sl_tp(sb, position, 628.0, "stop_loss")

    # Should have inserted a sell proposal (at least one insert call)
    assert sb.table.return_value.insert.called
    # Should have called execute_proposal
    mock_exec.assert_called_once()


# ── Bug 2: Config — SOL/XRP removed ──

def test_quant_symbols_excludes_sol_xrp():
    """Default quant_symbols should NOT include SOL or XRP (testnet 400 errors)."""
    from app.config import Settings
    s = Settings(
        supabase_url="https://test.supabase.co",
        supabase_service_role_key="test",
    )
    symbols = s.quant_symbols.upper()
    assert "SOLUSDT" not in symbols
    assert "XRPUSDT" not in symbols
    assert "BTCUSDT" in symbols
    assert "ETHUSDT" in symbols
    assert "BNBUSDT" in symbols


# ── Bug 3: ML signal_generator open_count ──

@pytest.mark.asyncio
async def test_ml_signals_counts_total_positions_not_unique_symbols():
    """_generate_ml_signals should count total open positions, not unique symbols.

    Setup: 3 open positions, 2 unique symbols, MAX_OPEN_POSITIONS=3.
    If buggy (counts unique): open_count=2 < 3 → buy allowed (WRONG)
    If fixed (counts total):  open_count=3 >= 3 → buy blocked (CORRECT)
    """
    mock_positions = [
        {"id": "1", "symbol": "BTCUSDT"},
        {"id": "2", "symbol": "BTCUSDT"},
        {"id": "3", "symbol": "ETHUSDT"},
    ]

    sb = MagicMock()
    pos_resp = MagicMock()
    pos_resp.data = mock_positions
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = pos_resp

    mock_ml_signal = [{"symbol": "BNBUSDT", "signal": "buy", "confidence": 0.8, "predicted_return": 0.01}]

    with patch("app.services.signal_generator.MAX_OPEN_POSITIONS", 3), \
         patch.dict("sys.modules", {"app.services.ml.signal_policy": MagicMock(get_ml_signals=AsyncMock(return_value=mock_ml_signal))}), \
         patch("app.services.signal_generator.binance_client") as mock_bc, \
         patch("app.services.signal_generator._submit_proposal", new_callable=AsyncMock) as mock_submit, \
         patch("app.services.signal_generator._cooled_down", return_value=True):
        mock_bc.get_price = AsyncMock(return_value={"price": "600.0"})

        from app.services.signal_generator import _generate_ml_signals
        await _generate_ml_signals(sb)

    # With 3 total positions and MAX=3, the buy should be BLOCKED
    mock_submit.assert_not_called()


# ── Fix 4: Trailing activation 40% → 65% ──

@pytest.mark.asyncio
async def test_trailing_does_NOT_activate_at_50pct():
    """Trailing should NOT activate at 50% progress (threshold now 65%)."""
    from app.services.trading_loop import _update_trailing_stop

    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    pos = {
        "id": "test-1", "symbol": "BTCUSDT",
        "entry_price": "100.0", "stop_loss_price": "95.0",
        "take_profit_price": "110.0", "current_quantity": "1.0",
    }

    await _update_trailing_stop(sb, pos, current_price=105.0, sl=95.0, tp=110.0)

    sb.table.return_value.update.assert_not_called()


@pytest.mark.asyncio
async def test_trailing_does_NOT_activate_at_60pct():
    """Trailing should NOT activate at 60% progress (threshold is 65%)."""
    from app.services.trading_loop import _update_trailing_stop

    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    pos = {
        "id": "test-1", "symbol": "BTCUSDT",
        "entry_price": "100.0", "stop_loss_price": "95.0",
        "take_profit_price": "110.0", "current_quantity": "1.0",
    }

    await _update_trailing_stop(sb, pos, current_price=106.0, sl=95.0, tp=110.0)

    sb.table.return_value.update.assert_not_called()


@pytest.mark.asyncio
async def test_trailing_activates_at_65pct():
    """Trailing SHOULD activate at 65% progress toward TP."""
    from app.services.trading_loop import _update_trailing_stop

    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    pos = {
        "id": "test-1", "symbol": "BTCUSDT",
        "entry_price": "100.0", "stop_loss_price": "95.0",
        "take_profit_price": "110.0", "current_quantity": "1.0",
    }

    await _update_trailing_stop(sb, pos, current_price=106.5, sl=95.0, tp=110.0)

    update_call = sb.table.return_value.update.call_args
    assert update_call is not None
    new_sl = update_call[0][0]["stop_loss_price"]
    # progress=0.65, trail_pct=0.65-0.30=0.35, new_sl=100+0.35*10=103.5
    assert new_sl == 103.5


# ── Fix 5: Cooldown 1h → 3h ──

def test_cooldown_is_3_hours():
    """Signal cooldown should be 180 minutes (3 hours), not 60."""
    from app.services.signal_generator import SIGNAL_COOLDOWN_MINUTES
    assert SIGNAL_COOLDOWN_MINUTES == 180


# ── Fix 6: ADX min 15 → 20 ──

def test_adx_min_is_20():
    """Default buy_adx_min should be 20.0, not 15.0."""
    from app.config import Settings
    s = Settings(
        supabase_url="https://test.supabase.co",
        supabase_service_role_key="test",
    )
    assert s.buy_adx_min == 20.0
