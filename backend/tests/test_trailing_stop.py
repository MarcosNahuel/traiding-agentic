"""Tests para trailing stop logic en trading_loop._update_trailing_stop.

RED-GREEN-REFACTOR: estos tests fueron escritos ANTES de verificar la implementación.

Escenarios:
1. No mover SL si precio está por debajo del entry (no hay ganancia)
2. No mover SL si progreso < 40% del camino al TP
3. Mover SL cuando progreso >= 40% hacia TP
4. Nunca bajar SL (solo subir)
5. No mover SL si falta SL o TP
6. SL sube proporcionalmente al progreso
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone


def _position(entry_price=100.0, sl=95.0, tp=110.0, symbol="BTCUSDT", pos_id="test-123"):
    """Helper: crea posición mock."""
    return {
        "id": pos_id,
        "symbol": symbol,
        "entry_price": str(entry_price),
        "stop_loss_price": str(sl),
        "take_profit_price": str(tp),
        "current_quantity": "1.0",
        "status": "open",
    }


def _mock_supabase():
    """Helper: supabase mock que trackea updates."""
    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    return sb


@pytest.mark.asyncio
async def test_no_trailing_when_price_below_entry():
    """Si el precio actual está por debajo del entry, no mover SL."""
    from app.services.trading_loop import _update_trailing_stop

    sb = _mock_supabase()
    pos = _position(entry_price=100.0, sl=95.0, tp=110.0)

    await _update_trailing_stop(sb, pos, current_price=98.0, sl=95.0, tp=110.0)

    sb.table.return_value.update.assert_not_called()


@pytest.mark.asyncio
async def test_no_trailing_when_progress_below_40pct():
    """Si el precio subió menos del 40% del camino al TP, no mover SL."""
    from app.services.trading_loop import _update_trailing_stop

    sb = _mock_supabase()
    # Entry=100, TP=110, distancia=10. 30% del camino = precio 103.
    pos = _position(entry_price=100.0, sl=95.0, tp=110.0)

    await _update_trailing_stop(sb, pos, current_price=103.0, sl=95.0, tp=110.0)

    sb.table.return_value.update.assert_not_called()


@pytest.mark.asyncio
async def test_no_trailing_at_30pct_progress():
    """30% no es suficiente para activar trailing (threshold es 40%)."""
    from app.services.trading_loop import _update_trailing_stop

    sb = _mock_supabase()
    # Entry=100, TP=110, distancia=10. 30% = precio 103.
    pos = _position(entry_price=100.0, sl=95.0, tp=110.0)

    await _update_trailing_stop(sb, pos, current_price=103.0, sl=95.0, tp=110.0)

    # NO debe haber llamado update (threshold es 40%)
    sb.table.return_value.update.assert_not_called()


@pytest.mark.asyncio
async def test_trailing_sl_proportional_to_progress():
    """Al 70% del camino al TP, SL = entry + 40% de la distancia."""
    from app.services.trading_loop import _update_trailing_stop

    sb = _mock_supabase()
    # Entry=100, TP=110, distancia=10. 70% = precio 107.
    pos = _position(entry_price=100.0, sl=95.0, tp=110.0)

    await _update_trailing_stop(sb, pos, current_price=107.0, sl=95.0, tp=110.0)

    update_call = sb.table.return_value.update.call_args
    new_sl = update_call[0][0]["stop_loss_price"]
    # progress=0.70, trail_pct=0.70-0.30=0.40, new_sl=100+0.40*10=104.0
    assert new_sl == 104.0


@pytest.mark.asyncio
async def test_trailing_never_lowers_sl():
    """Si el SL actual ya es más alto que el trailing calculado, no bajar."""
    from app.services.trading_loop import _update_trailing_stop

    sb = _mock_supabase()
    # Entry=100, TP=110. SL ya está en 103 (trailing previo).
    # Precio ahora 104 → trail_pct=0.10, new_sl=101.0 < 103 actual.
    pos = _position(entry_price=100.0, sl=103.0, tp=110.0)

    await _update_trailing_stop(sb, pos, current_price=104.0, sl=103.0, tp=110.0)

    sb.table.return_value.update.assert_not_called()


@pytest.mark.asyncio
async def test_trailing_does_raise_sl_when_higher():
    """Si el trailing calculado es mayor que el SL actual, sí subir."""
    from app.services.trading_loop import _update_trailing_stop

    sb = _mock_supabase()
    # Entry=100, TP=110. SL en 95. Precio 107 → new_sl=104 > 95.
    pos = _position(entry_price=100.0, sl=95.0, tp=110.0)

    await _update_trailing_stop(sb, pos, current_price=107.0, sl=95.0, tp=110.0)

    update_call = sb.table.return_value.update.call_args
    new_sl = update_call[0][0]["stop_loss_price"]
    assert new_sl > 95.0


@pytest.mark.asyncio
async def test_no_trailing_without_sl():
    """Si SL es None, no hacer trailing."""
    from app.services.trading_loop import _update_trailing_stop

    sb = _mock_supabase()
    pos = _position(entry_price=100.0, sl=95.0, tp=110.0)

    await _update_trailing_stop(sb, pos, current_price=107.0, sl=None, tp=110.0)

    sb.table.return_value.update.assert_not_called()


@pytest.mark.asyncio
async def test_no_trailing_without_tp():
    """Si TP es None, no hacer trailing."""
    from app.services.trading_loop import _update_trailing_stop

    sb = _mock_supabase()
    pos = _position(entry_price=100.0, sl=95.0, tp=110.0)

    await _update_trailing_stop(sb, pos, current_price=107.0, sl=95.0, tp=None)

    sb.table.return_value.update.assert_not_called()


@pytest.mark.asyncio
async def test_trailing_at_90pct_progress():
    """Al 90% del camino al TP, SL protege 60% de la ganancia."""
    from app.services.trading_loop import _update_trailing_stop

    sb = _mock_supabase()
    # Entry=1000, TP=1200, distancia=200. 90% = precio 1180.
    pos = _position(entry_price=1000.0, sl=900.0, tp=1200.0)

    await _update_trailing_stop(sb, pos, current_price=1180.0, sl=900.0, tp=1200.0)

    update_call = sb.table.return_value.update.call_args
    new_sl = update_call[0][0]["stop_loss_price"]
    # progress=0.90, trail_pct=0.90-0.30=0.60, new_sl=1000+0.60*200=1120.0
    assert new_sl == 1120.0


@pytest.mark.asyncio
async def test_trailing_with_real_crypto_prices():
    """Test con precios realistas de BTC."""
    from app.services.trading_loop import _update_trailing_stop

    sb = _mock_supabase()
    # BTC: entry=68000, SL=67000 (ATR-based), TP=70000
    # Precio sube a 69400 → 70% del camino
    pos = _position(entry_price=68000.0, sl=67000.0, tp=70000.0)

    await _update_trailing_stop(sb, pos, current_price=69400.0, sl=67000.0, tp=70000.0)

    update_call = sb.table.return_value.update.call_args
    new_sl = update_call[0][0]["stop_loss_price"]
    # progress=0.70, trail_pct=0.40, new_sl=68000+0.40*2000=68800
    assert new_sl == 68800.0
    # SL ahora en 68800 → profit protegido de $800 sobre entry
