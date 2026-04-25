"""Drift guard between LLM_SAFE_BOUNDS and TradingConfigOverride schema.

This test fails if anyone edits the schema without updating the bounds dict
(or vice versa). The schema MUST source its Field(ge=, le=) constraints
programmatically from LLM_SAFE_BOUNDS — never hardcoded.
"""

from app.services.llm_bounds import LLM_SAFE_BOUNDS
from agents.daily_strategist.schemas import TradingConfigOverride


def _extract_ge_le(field_info) -> tuple[float, float]:
    ge_val = None
    le_val = None
    for meta in field_info.metadata:
        if hasattr(meta, "ge") and meta.ge is not None:
            ge_val = meta.ge
        if hasattr(meta, "le") and meta.le is not None:
            le_val = meta.le
    return ge_val, le_val


def test_bounds_keys_match_schema_fields():
    assert set(LLM_SAFE_BOUNDS.keys()) == set(TradingConfigOverride.model_fields.keys())


def test_each_field_bounds_match_dict():
    for key, (lo, hi) in LLM_SAFE_BOUNDS.items():
        field = TradingConfigOverride.model_fields[key]
        ge_val, le_val = _extract_ge_le(field)
        assert ge_val == lo, f"{key}: schema ge={ge_val} != bounds lo={lo}"
        assert le_val == hi, f"{key}: schema le={le_val} != bounds hi={hi}"
