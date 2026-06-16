"""Guard de dust: exits por debajo del minNotional de Binance NO deben mandar orden.

Root cause del bug: _execute_sl_tp arma una SELL MARKET con la cantidad residual
(ej. 0.0001 ETH = ~$0.18) sin chequear minNotional. Binance la rechaza con 400 y,
como la posición sigue 'open', el fast-loop la regenera cada tick -> miles de
execution_error critical. El fix cierra la posición (write-off) sin mandar orden.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def test_meets_min_notional_detects_dust():
    from app.utils.binance_utils import meets_min_notional, is_dust
    # 0.0001 ETH @ ~1800 = $0.18 -> dust (orden no ejecutable)
    assert is_dust("ETHUSDT", 0.0001, 1800.0)
    assert not meets_min_notional("ETHUSDT", 0.0001, 1800.0)
    # exit real ~$72 -> ejecutable
    assert meets_min_notional("ETHUSDT", 0.04, 1800.0)
    # símbolo desconocido usa default
    assert is_dust("FOOUSDT", 0.0001, 1.0)


def _supabase_no_pending():
    """Mock supabase: la consulta anti-spam de proposals devuelve vacío."""
    mock = MagicMock()
    empty = MagicMock()
    empty.data = []
    # cadena exacta del anti-spam: select.eq.eq.gte.in_.execute
    (mock.table.return_value.select.return_value.eq.return_value.eq.return_value
     .gte.return_value.in_.return_value.execute.return_value) = empty
    return mock


@pytest.mark.asyncio
async def test_execute_sl_tp_dust_writes_off_without_order():
    """qty dust -> marca closed + registra dust_write_off, NO ejecuta orden."""
    from app.services import trading_loop

    pos = {"id": "abcd1234" * 4, "symbol": "ETHUSDT",
           "current_quantity": 0.0001, "entry_price": 1800.0}
    supabase = _supabase_no_pending()

    with patch("app.services.executor.execute_proposal", new_callable=AsyncMock) as exec_mock:
        await trading_loop._execute_sl_tp(supabase, pos, 1800.0, "stop_loss")

    # NO se ejecutó ninguna orden (root cause: el fast-loop regeneraba la SELL imposible)
    exec_mock.assert_not_called()
    # se tocaron positions (close) y risk_events (write-off log)
    tables = [c.args[0] for c in supabase.table.call_args_list]
    assert "positions" in tables
    assert "risk_events" in tables
    # la posición quedó cerrada por write-off
    update_arg = supabase.table.return_value.update.call_args.args[0]
    assert update_arg["status"] == "closed"
    assert update_arg["current_quantity"] == 0


@pytest.mark.asyncio
async def test_validate_proposal_rejects_dust_exit():
    """Defensa en profundidad: validate_proposal marca size invalido para exits dust."""
    with patch("app.services.risk_manager.get_supabase", return_value=MagicMock()), \
         patch("app.services.binance_client.get_account", new_callable=AsyncMock,
               return_value={"balances": [{"asset": "USDT", "free": "0.0"}]}):
        from app.services.risk_manager import validate_proposal
        result = await validate_proposal(
            trade_type="sell", symbol="ETHUSDT",
            quantity=0.0001, notional=0.18, current_price=1800.0,
            is_exit=True,
        )
    size_check = next(c for c in result.checks if c.name == "position_size")
    assert size_check.passed is False
