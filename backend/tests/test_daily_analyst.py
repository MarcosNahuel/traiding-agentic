"""Tests para el Daily LLM Analyst — Foundation (Phase 1).

Tests for: models bounds, config bridge, signal generator dynamic thresholds.
"""

import pytest
import time
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


# ════════════════════════════════════════════════════════════════════
# Models: bounds validation
# ════════════════════════════════════════════════════════════════════

def test_config_override_default_values():
    """TradingConfigOverride should have sensible defaults."""
    from app.services.daily_analyst.models import TradingConfigOverride
    config = TradingConfigOverride()
    assert config.buy_adx_min == 20.0
    assert config.buy_entropy_max == 0.85
    assert config.buy_rsi_max == 50.0
    assert config.signal_cooldown_minutes == 180


def test_config_override_rejects_out_of_bounds():
    """Values outside hard bounds should be rejected by Pydantic."""
    from app.services.daily_analyst.models import TradingConfigOverride
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TradingConfigOverride(buy_adx_min=5.0)  # min is 10

    with pytest.raises(ValidationError):
        TradingConfigOverride(buy_entropy_max=1.5)  # max is 0.95

    with pytest.raises(ValidationError):
        TradingConfigOverride(risk_multiplier=5.0)  # max is 2.0


def test_validate_bounds_clamps_extreme_values():
    """validate_bounds() should clamp values to safe range."""
    from app.services.daily_analyst.models import validate_bounds

    raw = {"buy_adx_min": 5.0, "buy_entropy_max": 1.0, "risk_multiplier": 0.1}
    clamped, warnings = validate_bounds(raw)

    assert clamped["buy_adx_min"] == 10.0
    assert clamped["buy_entropy_max"] == 0.95
    assert clamped["risk_multiplier"] == 0.25
    assert len(warnings) == 3


def test_validate_bounds_passes_valid_values():
    """Valid values should not be clamped."""
    from app.services.daily_analyst.models import validate_bounds

    raw = {"buy_adx_min": 25.0, "buy_entropy_max": 0.80}
    clamped, warnings = validate_bounds(raw)

    assert clamped["buy_adx_min"] == 25.0
    assert clamped["buy_entropy_max"] == 0.80
    assert len(warnings) == 0


# ════════════════════════════════════════════════════════════════════
# Config bridge: cache behavior
# ════════════════════════════════════════════════════════════════════

def test_config_bridge_returns_none_when_no_table():
    """Should return None gracefully when DB fails."""
    from app.services.daily_analyst.config_bridge import load_active_config, invalidate_cache
    invalidate_cache()

    with patch("app.services.daily_analyst.config_bridge.get_supabase", create=True, side_effect=Exception("no table")):
        result = load_active_config()

    assert result is None


def test_config_bridge_returns_override_from_db():
    """Should return TradingConfigOverride when active config exists in DB."""
    from app.services.daily_analyst.config_bridge import load_active_config, invalidate_cache
    invalidate_cache()

    sb = MagicMock()
    resp = MagicMock()
    resp.data = [{"buy_adx_min": 25.0, "buy_entropy_max": 0.75, "buy_rsi_max": 45.0,
                  "sell_rsi_min": 70.0, "signal_cooldown_minutes": 240,
                  "sl_atr_multiplier": 1.5, "tp_atr_multiplier": 2.0,
                  "risk_multiplier": 0.8, "max_open_positions": 3,
                  "quant_symbols": "BTCUSDT,ETHUSDT", "reasoning": "test"}]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = resp

    with patch("app.db.get_supabase", return_value=sb):
        result = load_active_config()

    assert result is not None
    assert result.buy_adx_min == 25.0
    assert result.buy_entropy_max == 0.75


def test_config_bridge_cache_avoids_db_hit():
    """Second call within 60s should use cache, not hit DB."""
    from app.services.daily_analyst.config_bridge import load_active_config, invalidate_cache
    invalidate_cache()

    sb = MagicMock()
    resp = MagicMock()
    resp.data = [{"buy_adx_min": 30.0, "buy_entropy_max": 0.70}]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = resp

    with patch("app.db.get_supabase", return_value=sb):
        result1 = load_active_config()
        result2 = load_active_config()

    # DB hit only once (second uses cache)
    assert sb.table.call_count == 1
    assert result1 is result2


# ════════════════════════════════════════════════════════════════════
# Signal generator: dynamic thresholds
# ════════════════════════════════════════════════════════════════════

def test_get_thresholds_defaults_when_no_override():
    """_get_thresholds should return defaults when no LLM config active."""
    from app.services.signal_generator import _get_thresholds

    with patch("app.services.daily_analyst.config_bridge.load_active_config", return_value=None):
        t = _get_thresholds()

    assert t["buy_rsi_max"] == 50.0
    assert t["signal_cooldown_minutes"] == 180


def test_get_thresholds_uses_override():
    """_get_thresholds should return LLM override values when active."""
    from app.services.signal_generator import _get_thresholds
    from app.services.daily_analyst.models import TradingConfigOverride

    override = TradingConfigOverride(buy_adx_min=30.0, buy_entropy_max=0.70, buy_rsi_max=40.0)

    with patch("app.services.daily_analyst.config_bridge.load_active_config", return_value=override):
        t = _get_thresholds()

    assert t["buy_adx_min"] == 30.0
    assert t["buy_entropy_max"] == 0.70
    assert t["buy_rsi_max"] == 40.0


# ════════════════════════════════════════════════════════════════════
# Config settings
# ════════════════════════════════════════════════════════════════════

def test_analyst_settings_exist():
    """Config should include analyst_enabled, analyst_model_name, google_ai_api_key."""
    from app.config import Settings
    s = Settings(
        supabase_url="https://test.supabase.co",
        supabase_service_role_key="test",
    )
    assert s.analyst_enabled is True  # Daily analyst activo por default
    assert s.analyst_model_name == "gemini-3.1-flash-lite-preview"
    assert s.google_ai_api_key == ""


# ════════════════════════════════════════════════════════════════════
# Scheduler: timing windows
# ════════════════════════════════════════════════════════════════════

def test_scheduler_pre_market_runs_at_0400_utc():
    """Pre-market should trigger at 04:00-04:02 UTC."""
    from app.services.daily_analyst.scheduler import should_run_pre_market
    import app.services.daily_analyst.scheduler as sched
    sched._pre_market_ran_today = ""

    at_0400 = datetime(2026, 3, 29, 4, 0, tzinfo=timezone.utc)
    at_0401 = datetime(2026, 3, 29, 4, 1, tzinfo=timezone.utc)
    at_0402 = datetime(2026, 3, 29, 4, 2, tzinfo=timezone.utc)
    at_0300 = datetime(2026, 3, 29, 3, 0, tzinfo=timezone.utc)
    at_2300 = datetime(2026, 3, 29, 23, 0, tzinfo=timezone.utc)

    assert should_run_pre_market(at_0400) is True
    sched._pre_market_ran_today = ""  # Reset
    assert should_run_pre_market(at_0401) is True
    sched._pre_market_ran_today = ""
    assert should_run_pre_market(at_0402) is False  # >= 2 min
    sched._pre_market_ran_today = ""
    assert should_run_pre_market(at_0300) is False  # Wrong hour
    sched._pre_market_ran_today = ""
    assert should_run_pre_market(at_2300) is False  # Old time, should NOT trigger


def test_scheduler_post_market_runs_at_0300_utc():
    """Post-market audit should trigger at 03:00-03:05 UTC."""
    from app.services.daily_analyst.scheduler import should_run_post_market
    import app.services.daily_analyst.scheduler as sched
    sched._post_market_ran_today = ""

    at_0300 = datetime(2026, 3, 29, 3, 0, tzinfo=timezone.utc)
    at_0304 = datetime(2026, 3, 29, 3, 4, tzinfo=timezone.utc)
    at_0305 = datetime(2026, 3, 29, 3, 5, tzinfo=timezone.utc)
    at_0005 = datetime(2026, 3, 29, 0, 5, tzinfo=timezone.utc)

    assert should_run_post_market(at_0300) is True
    sched._post_market_ran_today = ""
    assert should_run_post_market(at_0304) is True
    sched._post_market_ran_today = ""
    assert should_run_post_market(at_0305) is False  # >= 5 min
    sched._post_market_ran_today = ""
    assert should_run_post_market(at_0005) is False  # Old time, should NOT trigger


def test_scheduler_prevents_double_run():
    """Scheduler should not run twice on the same day."""
    from app.services.daily_analyst.scheduler import should_run_pre_market
    import app.services.daily_analyst.scheduler as sched
    sched._pre_market_ran_today = ""

    now = datetime(2026, 3, 29, 4, 0, tzinfo=timezone.utc)
    assert should_run_pre_market(now) is True
    sched._pre_market_ran_today = "2026-03-29"
    assert should_run_pre_market(now) is False


# ════════════════════════════════════════════════════════════════════
# Tools: get_ml_review
# ════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ml_review_returns_disable_when_no_data():
    """get_ml_review should recommend DISABLE when no training data exists."""
    import json

    sb = MagicMock()
    # ml_training_runs — empty
    run_resp = MagicMock()
    run_resp.data = []
    # ml_predictions — empty
    pred_resp = MagicMock()
    pred_resp.data = []

    sb.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = run_resp
    sb.table.return_value.select.return_value.gte.return_value.limit.return_value.execute.return_value = pred_resp

    with patch("app.db.get_supabase", return_value=sb):
        from app.services.daily_analyst.tools import get_ml_review
        result = await get_ml_review.ainvoke("")

    data = json.loads(result)
    assert "INSUFFICIENT DATA" in data["recommendation"]


@pytest.mark.asyncio
async def test_ml_review_recommends_enable_when_hit_rate_good():
    """get_ml_review should recommend ENABLE when hit rate > 50%."""
    import json

    sb = MagicMock()
    run_resp = MagicMock()
    run_resp.data = [{"created_at": "2026-03-29", "mean_sharpe": 1.5,
                      "mean_hit_rate": 0.55, "mean_mae": 0.001, "n_folds": 10}]
    # 60 predictions, 35 correct direction (58% hit rate)
    pred_resp = MagicMock()
    pred_resp.data = [{"y_true": 0.001, "y_pred": 0.0005}] * 35 + \
                     [{"y_true": -0.001, "y_pred": 0.0005}] * 25

    table_mock = MagicMock()
    # First call: ml_training_runs query
    table_mock.select.return_value.order.return_value.limit.return_value.execute.return_value = run_resp
    # Second call: ml_predictions query
    table_mock.select.return_value.gte.return_value.limit.return_value.execute.return_value = pred_resp
    sb.table.return_value = table_mock

    with patch("app.db.get_supabase", return_value=sb):
        from app.services.daily_analyst.tools import get_ml_review
        result = await get_ml_review.ainvoke("")

    data = json.loads(result)
    assert "ENABLE" in data["recommendation"]


# ════════════════════════════════════════════════════════════════════
# Tools: get_daily_research
# ════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_daily_research_returns_json():
    """get_daily_research should return valid JSON with expected structure."""
    import json
    from unittest.mock import AsyncMock

    sb = MagicMock()
    strat_resp = MagicMock()
    strat_resp.data = [{"name": "SMA Cross", "strategy_type": "trend", "confidence": 0.8}]
    src_resp = MagicMock()
    src_resp.data = [{"title": "151 Strategies", "source_type": "paper",
                      "status": "processed", "tags": ["momentum"]}]

    # Separate table mocks for strategies_found and sources
    call_count = {"n": 0}
    original_table = sb.table

    def table_router(name):
        mock = MagicMock()
        call_count["n"] += 1
        if name == "strategies_found":
            mock.select.return_value.order.return_value.limit.return_value.execute.return_value = strat_resp
        elif name == "sources":
            mock.select.return_value.order.return_value.limit.return_value.execute.return_value = src_resp
        return mock

    sb.table.side_effect = table_router

    # Mock httpx to avoid network calls
    mock_response = MagicMock()
    mock_response.text = "<rss></rss>"
    mock_http = AsyncMock()
    mock_http.get.return_value = mock_response

    with patch("app.db.get_supabase", return_value=sb), \
         patch("app.services.daily_analyst.tools.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        from app.services.daily_analyst.tools import get_daily_research
        result = await get_daily_research.ainvoke("")

    data = json.loads(result)
    assert "known_strategies" in data
    assert "recent_sources" in data
    assert "research_guidance" in data
    assert data["known_strategies"][0]["name"] == "SMA Cross"


# ════════════════════════════════════════════════════════════════════
# Tools: ALL_TOOLS has 9 entries
# ════════════════════════════════════════════════════════════════════

def test_all_tools_has_9_entries():
    """ALL_TOOLS should export exactly 9 tools including ML and research."""
    from app.services.daily_analyst.tools import ALL_TOOLS
    assert len(ALL_TOOLS) == 9
    tool_names = [t.name for t in ALL_TOOLS]
    assert "get_ml_review" in tool_names
    assert "get_daily_research" in tool_names


# ════════════════════════════════════════════════════════════════════
# Config: R:R safety rule
# ════════════════════════════════════════════════════════════════════

def test_tp_must_be_at_least_2x_sl():
    """tp_atr_multiplier default should be >= 2x sl_atr_multiplier for positive expectancy."""
    from app.config import Settings
    s = Settings(
        supabase_url="https://test.supabase.co",
        supabase_service_role_key="test",
    )
    assert s.tp_atr_multiplier >= 2.0 * s.sl_atr_multiplier, \
        f"R:R violation: TP {s.tp_atr_multiplier} < 2x SL {s.sl_atr_multiplier}"
