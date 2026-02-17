"""Unit tests for quant_orchestrator.py."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


def _reset_orchestrator():
    """Reset orchestrator global state between tests."""
    import app.services.quant_orchestrator as orch
    orch._tick_count = 0
    orch._last_tick_at = None
    orch._errors = []


def _mock_settings(enabled=True, symbols="BTCUSDT,ETHUSDT", interval="1h"):
    m = MagicMock()
    m.quant_enabled = enabled
    m.quant_symbols = symbols
    m.quant_primary_interval = interval
    m.entropy_threshold_ratio = 0.85
    m.sr_clusters = 8
    m.kelly_dampener = 0.5
    return m


def test_get_engine_status_initial_state():
    """Engine status should reflect 0 ticks and no errors at start."""
    _reset_orchestrator()
    with patch("app.services.quant_orchestrator.settings", _mock_settings()):
        from app.services.quant_orchestrator import get_engine_status
        status = get_engine_status()
    assert status.tick_count == 0
    assert status.last_tick_at is None
    assert status.errors == []
    assert status.enabled is True


def test_get_engine_status_modules_listed():
    """Engine status should list at least 5 quant modules."""
    _reset_orchestrator()
    with patch("app.services.quant_orchestrator.settings", _mock_settings()):
        from app.services.quant_orchestrator import get_engine_status
        status = get_engine_status()
    assert len(status.modules) >= 5


@pytest.mark.asyncio
async def test_run_quant_tick_increments_counter():
    """Each call to run_quant_tick should increment _tick_count by 1."""
    _reset_orchestrator()
    with patch("app.services.quant_orchestrator.settings", _mock_settings()), \
         patch("app.services.quant_orchestrator._collect_klines", new_callable=AsyncMock), \
         patch("app.services.quant_orchestrator._process_symbol", new_callable=AsyncMock):
        from app.services.quant_orchestrator import run_quant_tick
        await run_quant_tick()
        import app.services.quant_orchestrator as orch
        assert orch._tick_count == 1
        assert orch._last_tick_at is not None


@pytest.mark.asyncio
async def test_run_quant_tick_does_nothing_when_disabled():
    """run_quant_tick should be a no-op when quant_enabled=False."""
    _reset_orchestrator()
    with patch("app.services.quant_orchestrator.settings", _mock_settings(enabled=False)), \
         patch("app.services.quant_orchestrator._collect_klines", new_callable=AsyncMock) as mc:
        from app.services.quant_orchestrator import run_quant_tick
        await run_quant_tick()
        import app.services.quant_orchestrator as orch
        assert orch._tick_count == 0
        mc.assert_not_called()


@pytest.mark.asyncio
async def test_run_quant_tick_multiple_calls():
    """tick_count should increase with each call."""
    _reset_orchestrator()
    with patch("app.services.quant_orchestrator.settings", _mock_settings()), \
         patch("app.services.quant_orchestrator._collect_klines", new_callable=AsyncMock), \
         patch("app.services.quant_orchestrator._process_symbol", new_callable=AsyncMock):
        from app.services.quant_orchestrator import run_quant_tick
        await run_quant_tick()
        await run_quant_tick()
        await run_quant_tick()
        import app.services.quant_orchestrator as orch
        assert orch._tick_count == 3
