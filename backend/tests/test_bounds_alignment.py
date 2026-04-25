"""Verify that signal_generator and daily_analyst share the same bounds."""

from app.services.llm_bounds import LLM_SAFE_BOUNDS
from app.services.daily_analyst.models import PARAM_BOUNDS, TradingConfigOverride


def test_signal_generator_bounds_match_single_source():
    # signal_generator imports from llm_bounds, so test that the import
    # is referentially the same object (not a copy that could drift).
    from app.services.signal_generator import LLM_SAFE_BOUNDS as SG_BOUNDS
    assert SG_BOUNDS is LLM_SAFE_BOUNDS, (
        "signal_generator.LLM_SAFE_BOUNDS should be the imported singleton, "
        "not a copy. If you see this fail, check the import statement in "
        "signal_generator.py — it should be `from .llm_bounds import LLM_SAFE_BOUNDS`."
    )


def test_param_bounds_is_llm_safe_bounds():
    assert PARAM_BOUNDS is LLM_SAFE_BOUNDS, (
        "daily_analyst PARAM_BOUNDS must be the same object as LLM_SAFE_BOUNDS."
    )


def test_pydantic_field_constraints_match_bounds():
    """Each Pydantic Field's ge/le should match LLM_SAFE_BOUNDS."""
    schema = TradingConfigOverride.model_json_schema()
    properties = schema.get("properties", {})

    field_to_bound = {
        "buy_rsi_max": "buy_rsi_max",
        "buy_adx_min": "buy_adx_min",
        "buy_entropy_max": "buy_entropy_max",
        "sell_rsi_min": "sell_rsi_min",
        "signal_cooldown_minutes": "signal_cooldown_minutes",
        "sl_atr_multiplier": "sl_atr_multiplier",
        "tp_atr_multiplier": "tp_atr_multiplier",
        "risk_multiplier": "risk_multiplier",
        "max_open_positions": "max_open_positions",
    }

    for field, bound_key in field_to_bound.items():
        lo, hi = LLM_SAFE_BOUNDS[bound_key]
        prop = properties.get(field, {})
        assert prop.get("minimum") == lo, (
            f"{field} minimum={prop.get('minimum')} != LLM_SAFE_BOUNDS lo={lo}"
        )
        assert prop.get("maximum") == hi, (
            f"{field} maximum={prop.get('maximum')} != LLM_SAFE_BOUNDS hi={hi}"
        )
