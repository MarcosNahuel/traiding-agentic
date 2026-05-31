"""Unit tests for the Daily Strategist decision schema + bounds clamping + markdown."""

import pytest


def test_tweak_clamps_proposed_config_to_safe_bounds():
    from app.services.strategist.schemas import StrategistDecision

    d = StrategistDecision(
        decision="TWEAK_PARAMS",
        confidence=0.7,
        summary="tighten entries in chop",
        evidence=["ETH WR 78%/9 trades", "funding flipped negative 36h ago", "F&G 72->48"],
        proposed_config={"buy_adx_min": 100.0},  # absurd, must clamp to 40 (PARAM_BOUNDS max)
    )
    clamped, warnings = d.clamped_config()
    assert clamped["buy_adx_min"] == 40.0
    assert any("buy_adx_min" in w for w in warnings)


def test_arbitrary_keys_are_dropped_not_clamped():
    """F2 (jury): claves fuera de PARAM_BOUNDS deben descartarse, no pasar al insert."""
    from app.services.strategist.schemas import StrategistDecision

    d = StrategistDecision(
        decision="TWEAK_PARAMS",
        confidence=0.7,
        summary="x",
        evidence=["a", "b", "c"],
        proposed_config={"buy_adx_min": 25.0, "trading_enabled": True, "risk_max_daily_loss": 9999},
    )
    clamped, warnings = d.clamped_config()
    assert clamped["buy_adx_min"] == 25.0
    assert "trading_enabled" not in clamped
    assert "risk_max_daily_loss" not in clamped
    assert any("trading_enabled" in w for w in warnings)


def test_keep_as_is_has_no_config():
    from app.services.strategist.schemas import StrategistDecision

    d = StrategistDecision(decision="KEEP_AS_IS", confidence=0.6, summary="hold", evidence=[])
    assert d.proposed_config is None
    clamped, warnings = d.clamped_config()
    assert clamped == {}
    assert warnings == []


def test_invalid_decision_type_rejected():
    from pydantic import ValidationError

    from app.services.strategist.schemas import StrategistDecision

    with pytest.raises(ValidationError):
        StrategistDecision(decision="DEPLOY_TO_MAINNET", confidence=0.9, summary="x", evidence=[])


def test_render_markdown_has_key_sections():
    from app.services.strategist.schemas import StrategistDecision

    d = StrategistDecision(
        decision="TWEAK_PARAMS",
        confidence=0.8,
        summary="tighten ADX in ranging regime",
        evidence=["ETH WR 78%/9", "funding negative", "F&G 48"],
        proposed_config={"buy_adx_min": 25.0},
        risks="small sample (9 trades) — fragile",
        macro_context="F&G 48 (fear), BTC funding flipping negative",
    )
    md = d.render_markdown(run_at_iso="2026-05-30T06:00:00Z")
    assert "# Strategist Evaluation" in md
    assert "2026-05-30" in md
    assert "TWEAK_PARAMS" in md
    assert "buy_adx_min" in md
    assert "fragile" in md
    assert "F&G 48" in md  # macro context rendered
