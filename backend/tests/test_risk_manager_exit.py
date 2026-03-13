"""Tests para is_exit en risk_manager.py — exits no deben bloquearse por checks de entrada."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def _make_supabase(usdt_free=0.0, open_positions=3, daily_pnl=-300.0):
    """Supabase simulando cuenta sin USDT, posiciones llenas y daily loss excedido."""
    mock = MagicMock()

    # positions count
    positions_resp = MagicMock()
    positions_resp.data = [{"id": str(i)} for i in range(open_positions)]

    # account_snapshots daily PnL
    snap_resp = MagicMock()
    snap_resp.data = [{"daily_pnl": str(daily_pnl)}]

    # entry_notional
    notional_resp = MagicMock()
    notional_resp.data = [{"entry_notional": "300.0"}]

    def table_dispatch(name):
        t = MagicMock()
        if name == "positions":
            t.select.return_value.eq.return_value.execute.return_value = positions_resp
            t.select.return_value.eq.return_value.eq.return_value.execute.return_value = positions_resp
            t.select.return_value.eq.return_value.execute.return_value = notional_resp
        elif name == "account_snapshots":
            t.select.return_value.eq.return_value.execute.return_value = snap_resp
        return t

    mock.table.side_effect = table_dispatch
    return mock


def _bad_account():
    """Cuenta Binance sin USDT libre."""
    return {"balances": [{"asset": "USDT", "free": "0.0"}]}


@pytest.mark.asyncio
async def test_exit_bypasses_balance_check():
    """is_exit=True: balance USDT insuficiente no debe bloquear el exit."""
    with patch("app.services.risk_manager.get_supabase", return_value=_make_supabase(usdt_free=0.0)), \
         patch("app.services.binance_client.get_account", new_callable=AsyncMock, return_value=_bad_account()):

        from app.services.risk_manager import validate_proposal
        result = await validate_proposal(
            trade_type="sell", symbol="BTCUSDT",
            quantity=0.001, notional=50.0, current_price=50000.0,
            is_exit=True,
        )

    balance_check = next(c for c in result.checks if c.name == "account_balance")
    assert balance_check.passed is True
    assert "Exit" in balance_check.message


@pytest.mark.asyncio
async def test_exit_bypasses_max_open_positions():
    """is_exit=True: límite de posiciones abiertas no debe bloquear el exit."""
    with patch("app.services.risk_manager.get_supabase", return_value=_make_supabase(open_positions=5)), \
         patch("app.services.binance_client.get_account", new_callable=AsyncMock, return_value=_bad_account()), \
         patch("app.services.risk_manager.settings") as mock_settings:
        mock_settings.risk_min_position_size = 10.0
        mock_settings.risk_max_position_size = 500.0
        mock_settings.risk_max_open_positions = 3
        mock_settings.risk_max_positions_per_symbol = 1
        mock_settings.risk_max_account_utilization = 0.8
        mock_settings.risk_max_daily_loss = 200.0
        mock_settings.risk_auto_approval_threshold = 100.0

        from app.services.risk_manager import validate_proposal
        result = await validate_proposal(
            trade_type="sell", symbol="BTCUSDT",
            quantity=0.001, notional=50.0, current_price=50000.0,
            is_exit=True,
        )

    pos_check = next(c for c in result.checks if c.name == "max_open_positions")
    assert pos_check.passed is True
    assert "Exit" in pos_check.message


@pytest.mark.asyncio
async def test_exit_bypasses_daily_loss_limit():
    """is_exit=True: daily loss excedido no debe bloquear el exit."""
    with patch("app.services.risk_manager.get_supabase", return_value=_make_supabase(daily_pnl=-500.0)), \
         patch("app.services.binance_client.get_account", new_callable=AsyncMock, return_value=_bad_account()):

        from app.services.risk_manager import validate_proposal
        result = await validate_proposal(
            trade_type="sell", symbol="BTCUSDT",
            quantity=0.001, notional=50.0, current_price=50000.0,
            is_exit=True,
        )

    loss_check = next(c for c in result.checks if c.name == "daily_loss_limit")
    assert loss_check.passed is True
    assert "Exit" in loss_check.message


@pytest.mark.asyncio
async def test_entry_still_blocked_by_daily_loss():
    """is_exit=False: daily loss excedido debe seguir bloqueando entradas."""
    good_account = {"balances": [{"asset": "USDT", "free": "1000.0"}]}
    with patch("app.services.risk_manager.get_supabase", return_value=_make_supabase(daily_pnl=-500.0)), \
         patch("app.services.binance_client.get_account", new_callable=AsyncMock, return_value=good_account), \
         patch("app.services.risk_manager.settings") as mock_settings:
        mock_settings.risk_min_position_size = 10.0
        mock_settings.risk_max_position_size = 500.0
        mock_settings.risk_max_open_positions = 3
        mock_settings.risk_max_positions_per_symbol = 1
        mock_settings.risk_max_account_utilization = 0.8
        mock_settings.risk_max_daily_loss = 200.0
        mock_settings.risk_auto_approval_threshold = 100.0

        from app.services.risk_manager import validate_proposal
        result = await validate_proposal(
            trade_type="buy", symbol="BTCUSDT",
            quantity=0.001, notional=50.0, current_price=50000.0,
            is_exit=False,
        )

    loss_check = next(c for c in result.checks if c.name == "daily_loss_limit")
    assert loss_check.passed is False
