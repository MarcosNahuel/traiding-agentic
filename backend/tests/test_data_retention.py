"""Tests TDD para data_retention.py — limpieza automática de tablas grandes."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone


# ── should_run_retention ──────────────────────────────────────────────────────

def test_should_run_retention_at_2am_utc():
    """Retorna True a las 02:00 UTC (minuto 0-1)."""
    from app.services.data_retention import should_run_retention
    now = datetime(2026, 4, 6, 2, 0, tzinfo=timezone.utc)
    assert should_run_retention(now) is True


def test_should_run_retention_at_2am_minute_1():
    """Retorna True a las 02:01 UTC (dentro de ventana de 2 min)."""
    from app.services.data_retention import should_run_retention
    now = datetime(2026, 4, 6, 2, 1, tzinfo=timezone.utc)
    assert should_run_retention(now) is True


def test_should_not_run_retention_at_other_hours():
    """Retorna False fuera de las 02:xx UTC."""
    from app.services.data_retention import should_run_retention
    for hour in [0, 1, 3, 12, 23]:
        now = datetime(2026, 4, 6, hour, 0, tzinfo=timezone.utc)
        assert should_run_retention(now) is False, f"Should be False at hour {hour}"


def test_should_not_run_retention_twice_same_day():
    """Retorna False si ya se ejecutó hoy (evita doble limpieza)."""
    import app.services.data_retention as dr
    dr._last_retention_date = "2026-04-06"
    now = datetime(2026, 4, 6, 2, 0, tzinfo=timezone.utc)
    result = dr.should_run_retention(now)
    dr._last_retention_date = None  # cleanup
    assert result is False


# ── run_data_retention ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_retention_calls_supabase_rpc():
    """run_data_retention llama a supabase.rpc('run_data_retention')."""
    mock_sb = MagicMock()
    rpc_result = MagicMock()
    rpc_result.data = {"reconciliation_runs": 100, "klines_ohlcv": 50000}
    mock_sb.rpc.return_value.execute.return_value = rpc_result

    with patch("app.services.data_retention.get_supabase", return_value=mock_sb):
        from app.services.data_retention import run_data_retention
        result = await run_data_retention()

    mock_sb.rpc.assert_called_once_with("run_data_retention")
    assert result["reconciliation_runs"] == 100
    assert result["klines_ohlcv"] == 50000


@pytest.mark.asyncio
async def test_run_retention_handles_error_gracefully():
    """run_data_retention captura excepciones y retorna dict vacío."""
    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute.side_effect = Exception("connection error")

    with patch("app.services.data_retention.get_supabase", return_value=mock_sb):
        from app.services.data_retention import run_data_retention
        result = await run_data_retention()

    assert result == {}


@pytest.mark.asyncio
async def test_run_retention_marks_last_date():
    """Después de run_data_retention, _last_retention_date se actualiza a hoy."""
    import app.services.data_retention as dr
    dr._last_retention_date = None

    mock_sb = MagicMock()
    rpc_result = MagicMock()
    rpc_result.data = {}
    mock_sb.rpc.return_value.execute.return_value = rpc_result

    with patch("app.services.data_retention.get_supabase", return_value=mock_sb):
        await dr.run_data_retention()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert dr._last_retention_date == today
    dr._last_retention_date = None  # cleanup
