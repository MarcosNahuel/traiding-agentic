"""Tests for partial exit logic in trading_loop._maybe_take_partial_exit.

Behavior under test:
- When PARTIAL_EXIT_ENABLED=false: nothing happens, returns False.
- When current_price < entry + 1R: returns False, no DB write.
- When current_price >= entry + 1R AND partial_exit_taken=False:
    - Marks partial_exit_taken=True, partial_exit_price, partial_exit_qty=50% of current_quantity.
    - Moves SL to breakeven (entry_price).
    - Returns True.
- When partial_exit_taken=True already: returns False (idempotent).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def base_position():
    return {
        "id": "pos-uuid",
        "symbol": "BTCUSDT",
        "entry_price": 100.0,
        "stop_loss_price": 95.0,
        "take_profit_price": 110.0,
        "current_quantity": 1.0,
        "partial_exit_taken": False,
    }


@pytest.mark.asyncio
async def test_partial_exit_disabled_returns_false(base_position):
    from app.services.trading_loop import _maybe_take_partial_exit
    with patch("app.services.trading_loop.settings") as s:
        s.partial_exit_enabled = False
        s.partial_exit_fraction = 0.5
        s.partial_exit_at_r = 1.0
        result = await _maybe_take_partial_exit(MagicMock(), base_position, current_price=110.0)
    assert result is False


@pytest.mark.asyncio
async def test_partial_exit_below_1R_returns_false(base_position):
    from app.services.trading_loop import _maybe_take_partial_exit
    # entry=100, sl=95 → R=5. 1R = 105. current=104 → no trigger.
    with patch("app.services.trading_loop.settings") as s:
        s.partial_exit_enabled = True
        s.partial_exit_fraction = 0.5
        s.partial_exit_at_r = 1.0
        result = await _maybe_take_partial_exit(MagicMock(), base_position, current_price=104.0)
    assert result is False


@pytest.mark.asyncio
async def test_partial_exit_at_or_above_1R_triggers(base_position):
    from app.services.trading_loop import _maybe_take_partial_exit
    supabase = MagicMock()
    # Simulate update + insert succeeding.
    supabase.table().update().eq().execute.return_value = MagicMock(data=[base_position])
    supabase.table().insert().execute.return_value = MagicMock(data=[{"id": "prop-1"}])

    with patch("app.services.trading_loop.settings") as s, \
         patch("app.services.trading_loop._execute_sl_tp", new=AsyncMock()):
        s.partial_exit_enabled = True
        s.partial_exit_fraction = 0.5
        s.partial_exit_at_r = 1.0
        # entry=100, sl=95 → R=5. 1R = 105. current=105 → trigger.
        result = await _maybe_take_partial_exit(supabase, base_position, current_price=105.0)

    assert result is True


@pytest.mark.asyncio
async def test_partial_exit_idempotent_when_already_taken(base_position):
    base_position["partial_exit_taken"] = True
    from app.services.trading_loop import _maybe_take_partial_exit
    with patch("app.services.trading_loop.settings") as s:
        s.partial_exit_enabled = True
        s.partial_exit_fraction = 0.5
        s.partial_exit_at_r = 1.0
        result = await _maybe_take_partial_exit(MagicMock(), base_position, current_price=999.0)
    assert result is False
