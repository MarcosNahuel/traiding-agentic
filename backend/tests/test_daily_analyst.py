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
    """Config should include analyst_enabled, analyst_model_name, google_api_key."""
    from app.config import Settings
    s = Settings(
        supabase_url="https://test.supabase.co",
        supabase_service_role_key="test",
    )
    assert s.analyst_enabled is False
    assert s.analyst_model_name == "gemini-2.0-flash"
    assert s.google_api_key == ""
