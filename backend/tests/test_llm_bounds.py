"""Tests for backend.app.services.llm_bounds."""

import pytest
from app.services.llm_bounds import LLM_SAFE_BOUNDS, clamp, is_within_bounds


def test_bounds_dict_has_all_required_keys():
    required = {
        "buy_rsi_max", "buy_adx_min", "buy_entropy_max",
        "sell_rsi_min", "signal_cooldown_minutes",
        "sl_atr_multiplier", "tp_atr_multiplier",
        "risk_multiplier", "max_open_positions",
    }
    assert required.issubset(LLM_SAFE_BOUNDS.keys())


def test_bounds_are_tuples_of_two_floats():
    for key, val in LLM_SAFE_BOUNDS.items():
        assert isinstance(val, tuple), f"{key} not a tuple"
        assert len(val) == 2, f"{key} not length 2"
        lo, hi = val
        assert isinstance(lo, (int, float))
        assert isinstance(hi, (int, float))
        assert lo < hi, f"{key}: lo={lo} not < hi={hi}"


def test_clamp_within_bounds_returns_value():
    assert clamp("buy_rsi_max", 50.0) == 50.0


def test_clamp_below_min_returns_min():
    assert clamp("buy_rsi_max", 20.0) == 30.0


def test_clamp_above_max_returns_max():
    assert clamp("buy_rsi_max", 99.0) == 55.0


def test_clamp_unknown_key_raises():
    with pytest.raises(KeyError):
        clamp("nonexistent", 1.0)


def test_is_within_bounds_inside():
    assert is_within_bounds("buy_adx_min", 25.0) is True


def test_is_within_bounds_outside():
    assert is_within_bounds("buy_adx_min", 5.0) is False
    assert is_within_bounds("buy_adx_min", 99.0) is False


def test_is_within_bounds_unknown_key_returns_false():
    assert is_within_bounds("nonexistent", 1.0) is False


def test_clamp_at_boundaries():
    # Exact min and max should pass through unchanged
    lo, hi = LLM_SAFE_BOUNDS["buy_rsi_max"]
    assert clamp("buy_rsi_max", lo) == lo
    assert clamp("buy_rsi_max", hi) == hi
