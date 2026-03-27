"""Tests para los 4 issues pendientes de auditoría Mar 2026.

Issue 1: Partial fills — executor debe manejar PARTIALLY_FILLED
Issue 2: Commission conversion BNB→USDT
Issue 3: Reconciliation balance cross-check
Issue 4: Proposal TTL cleanup
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone, timedelta


# ════════════════════════════════════════════════════════════════════
# Issue 1: Partial fills
# ════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_partial_fill_does_not_mark_executed():
    """PARTIALLY_FILLED order should succeed with partial qty."""
    from app.services.executor import execute_proposal

    sb = MagicMock()
    claimed = MagicMock()
    claimed.data = [{"id": "p1", "symbol": "BTCUSDT", "type": "buy",
                     "quantity": "0.001", "price": "70000",
                     "order_type": "MARKET", "retry_count": 0}]
    sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = claimed
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

    with patch("app.services.executor.get_supabase", return_value=sb), \
         patch("app.services.executor.settings") as s, \
         patch("app.services.executor.binance_client") as bc, \
         patch("app.services.executor._open_position", new_callable=AsyncMock) as mock_open, \
         patch("app.services.executor._log_risk_event", new_callable=AsyncMock):
        s.trading_enabled = True
        s.risk_max_positions_per_symbol = 5
        s.risk_max_open_positions = 5
        s.quant_primary_interval = "1h"
        bc.place_order = AsyncMock(return_value={
            "orderId": 123,
            "status": "PARTIALLY_FILLED",
            "executedQty": "0.0005",
            "fills": [{"price": "70000", "commission": "0.0001", "commissionAsset": "USDT"}],
        })
        bc.get_price = AsyncMock(return_value={"price": "70000"})

        result = await execute_proposal("p1")

    assert result["success"] is True
    assert result["executed_quantity"] == 0.0005
    # _open_position called with partial qty
    mock_open.assert_called_once()
    assert mock_open.call_args[0][3] == 0.0005  # qty arg


@pytest.mark.asyncio
async def test_canceled_order_does_not_open_position():
    """CANCELED order should mark proposal as error, not open position."""
    from app.services.executor import execute_proposal

    sb = MagicMock()
    claimed = MagicMock()
    claimed.data = [{"id": "p2", "symbol": "BTCUSDT", "type": "buy",
                     "quantity": "0.001", "price": "70000",
                     "order_type": "MARKET", "retry_count": 0}]
    sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = claimed
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    with patch("app.services.executor.get_supabase", return_value=sb), \
         patch("app.services.executor.settings") as s, \
         patch("app.services.executor.binance_client") as bc, \
         patch("app.services.executor._open_position", new_callable=AsyncMock) as mock_open, \
         patch("app.services.executor._log_risk_event", new_callable=AsyncMock):
        s.trading_enabled = True
        s.risk_max_positions_per_symbol = 5
        s.risk_max_open_positions = 5
        bc.place_order = AsyncMock(return_value={
            "orderId": 456,
            "status": "CANCELED",
            "executedQty": "0",
            "fills": [],
        })

        result = await execute_proposal("p2")

    assert result["success"] is False
    mock_open.assert_not_called()


# ════════════════════════════════════════════════════════════════════
# Issue 2: Commission conversion
# ════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_bnb_commission_converted_to_usdt():
    """BNB commission should be converted to USDT equivalent."""
    from app.services.executor import _convert_commission_to_usdt

    with patch("app.services.executor.binance_client") as bc:
        bc.get_price = AsyncMock(return_value={"price": "600.0"})
        result = await _convert_commission_to_usdt(0.001, "BNB")

    # 0.001 BNB * $600 = $0.60
    assert result == pytest.approx(0.6, rel=0.01)


@pytest.mark.asyncio
async def test_usdt_commission_unchanged():
    """USDT commission should be returned as-is."""
    from app.services.executor import _convert_commission_to_usdt
    result = await _convert_commission_to_usdt(0.5, "USDT")
    assert result == 0.5


@pytest.mark.asyncio
async def test_commission_conversion_fallback_on_error():
    """If price fetch fails, return raw commission (don't crash)."""
    from app.services.executor import _convert_commission_to_usdt

    with patch("app.services.executor.binance_client") as bc:
        bc.get_price = AsyncMock(side_effect=Exception("no price"))
        result = await _convert_commission_to_usdt(0.001, "BNB")

    assert result == 0.001  # fallback to raw


# ════════════════════════════════════════════════════════════════════
# Issue 3: Reconciliation balance cross-check (no test — integración)
# Se testea indirectamente en test_reconciliation_balance
# ════════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════════
# Issue 4: Proposal TTL cleanup
# ════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_stale_proposals_get_expired():
    """Proposals older than 1h in draft/approved should be expired."""
    from app.services.reconciliation import _expire_stale_proposals

    sb = MagicMock()
    old_proposal = {"id": "old-1", "symbol": "BTCUSDT", "type": "buy", "status": "approved"}

    # select returns stale proposals for each status
    sb.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
        data=[old_proposal]
    )
    # update chain
    sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()

    count = await _expire_stale_proposals(sb)

    assert count >= 1
    # Verify update was called with expired status
    update_calls = sb.table.return_value.update.call_args_list
    assert any("expired" in str(c) for c in update_calls)


@pytest.mark.asyncio
async def test_fresh_proposals_not_expired():
    """Proposals less than 1h old should NOT be expired."""
    from app.services.reconciliation import _expire_stale_proposals

    sb = MagicMock()
    # No stale proposals found
    sb.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
        data=[]
    )

    count = await _expire_stale_proposals(sb)

    assert count == 0
    sb.table.return_value.update.assert_not_called()
