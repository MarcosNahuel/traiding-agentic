"""Pydantic schemas for the Daily Strategist agent."""

import sys
from pathlib import Path

# Ensure backend/ is on sys.path so we can import the SSOT bounds module.
_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from pydantic import BaseModel, ConfigDict, Field

from app.services.llm_bounds import LLM_SAFE_BOUNDS


def _b(key: str) -> tuple:
    return LLM_SAFE_BOUNDS[key]


class TradingConfigOverride(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    buy_rsi_max: float = Field(ge=_b("buy_rsi_max")[0], le=_b("buy_rsi_max")[1])
    buy_adx_min: float = Field(ge=_b("buy_adx_min")[0], le=_b("buy_adx_min")[1])
    buy_entropy_max: float = Field(ge=_b("buy_entropy_max")[0], le=_b("buy_entropy_max")[1])
    sell_rsi_min: float = Field(ge=_b("sell_rsi_min")[0], le=_b("sell_rsi_min")[1])
    signal_cooldown_minutes: int = Field(
        ge=_b("signal_cooldown_minutes")[0], le=_b("signal_cooldown_minutes")[1]
    )
    sl_atr_multiplier: float = Field(
        ge=_b("sl_atr_multiplier")[0], le=_b("sl_atr_multiplier")[1]
    )
    tp_atr_multiplier: float = Field(
        ge=_b("tp_atr_multiplier")[0], le=_b("tp_atr_multiplier")[1]
    )
    risk_multiplier: float = Field(
        ge=_b("risk_multiplier")[0], le=_b("risk_multiplier")[1]
    )
    max_open_positions: int = Field(
        ge=_b("max_open_positions")[0], le=_b("max_open_positions")[1]
    )
