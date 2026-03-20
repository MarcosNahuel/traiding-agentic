"""Tests para el atomic claim en executor.py — previene ejecución duplicada."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone


def _approved_proposal(proposal_id="prop-1"):
    return {
        "id": proposal_id,
        "symbol": "BTCUSDT",
        "type": "buy",
        "order_type": "MARKET",
        "quantity": "0.001",
        "price": "50000.0",
        "status": "approved",
        "retry_count": 0,
        "strategy_id": None,
    }


def _make_supabase(claim_succeeds: bool, proposal_id="prop-1"):
    mock = MagicMock()

    # Atomic claim response
    claim_resp = MagicMock()
    claim_resp.data = [_approved_proposal(proposal_id)] if claim_succeeds else []

    # Status check response (for when claim fails)
    status_resp = MagicMock()
    status_resp.data = [{"status": "executing"}]

    # Setup update chain (for atomic claim)
    mock.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = claim_resp

    # Setup select chain (status check when claim fails)
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value = status_resp

    # Other chains
    empty = MagicMock()
    empty.data = []
    mock.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "pos-1"}])
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    return mock


@pytest.mark.asyncio
async def test_atomic_claim_succeeds_places_order():
    """Cuando el claim atomico funciona, se debe ejecutar place_order."""
    mock_order = {
        "orderId": "123",
        "status": "FILLED",
        "fills": [{"price": "50000", "commission": "0.001", "commissionAsset": "BNB"}],
        "executedQty": "0.001",
        "price": "0",
    }
    with patch("app.services.executor.settings") as mock_settings, \
         patch("app.services.executor.get_supabase", return_value=_make_supabase(True)), \
         patch("app.services.executor.binance_client") as mock_bc, \
         patch("app.services.executor._log_risk_event", new_callable=AsyncMock), \
         patch("app.services.executor._open_position", new_callable=AsyncMock):
        mock_settings.trading_enabled = True
        mock_settings.quant_primary_interval = "1h"
        mock_settings.sl_atr_multiplier = 1.5
        mock_settings.tp_atr_multiplier = 3.0
        mock_settings.sl_fallback_pct = 0.03
        mock_settings.tp_fallback_pct = 0.06
        mock_settings.risk_max_positions_per_symbol = 1
        mock_settings.risk_max_open_positions = 5
        mock_bc.place_order = AsyncMock(return_value=mock_order)
        mock_bc.get_price = AsyncMock(return_value={"price": "50000"})

        from app.services.executor import execute_proposal
        result = await execute_proposal("prop-1")

    assert result["success"] is True
    mock_bc.place_order.assert_called_once()


@pytest.mark.asyncio
async def test_atomic_claim_blocked_if_already_executing():
    """Cuando el claim atomico falla (ya en 'executing'), no debe llamar place_order."""
    with patch("app.services.executor.settings") as mock_settings, \
         patch("app.services.executor.get_supabase", return_value=_make_supabase(False)), \
         patch("app.services.executor.binance_client") as mock_bc:
        mock_settings.trading_enabled = True
        mock_bc.place_order = AsyncMock()

        from app.services.executor import execute_proposal
        result = await execute_proposal("prop-1")

    assert result["success"] is False
    assert "not claimable" in result["error"]
    mock_bc.place_order.assert_not_called()
