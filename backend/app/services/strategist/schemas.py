"""Strategist decision schema + bounds clamping + evaluation markdown rendering."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from ..daily_analyst.models import validate_bounds

DecisionType = Literal[
    "KEEP_AS_IS",              # today's config = yesterday's active; no insert
    "TWEAK_PARAMS",            # propose new values within safe bounds (pending_approval)
    "PROPOSE_STRATEGY_CHANGE",  # structural recommendation in markdown; NO config insert
    "RECOMMEND_PAUSE",         # recommend pausing the bot; human acts (NO config insert)
]


class StrategistDecision(BaseModel):
    """The agent's daily verdict. Only TWEAK_PARAMS carries a config to insert."""

    decision: DecisionType
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    evidence: list[str] = Field(default_factory=list)
    proposed_config: Optional[dict] = None
    risks: str = ""
    data_quality: str = ""
    performance_review: str = ""
    macro_context: str = ""

    def clamped_config(self) -> tuple[dict, list[str]]:
        """Clamp the proposed config to PARAM_BOUNDS. Empty if no config proposed."""
        if not self.proposed_config:
            return {}, []
        return validate_bounds(self.proposed_config)

    def render_markdown(self, run_at_iso: str) -> str:
        date = run_at_iso[:10]
        clamped, warnings = self.clamped_config()
        lines = [
            f"# Strategist Evaluation — {date}",
            "",
            f"- **Run at:** {run_at_iso}",
            f"- **Decision:** `{self.decision}`",
            f"- **Confidence:** {self.confidence:.2f}",
            "",
            "## Summary",
            "",
            self.summary or "(none)",
            "",
            "## Data Quality",
            "",
            self.data_quality or "(no data quality notes)",
            "",
            "## Performance Review",
            "",
            self.performance_review or "(no review)",
            "",
            "## Macro Context",
            "",
            self.macro_context or "(no macro context)",
            "",
            "## Evidence",
            "",
        ]
        lines += [f"- {e}" for e in self.evidence] if self.evidence else ["(none cited)"]
        lines += ["", "## Proposed Config", ""]
        if clamped:
            lines += [f"- `{k}` = {v}" for k, v in clamped.items()]
            if warnings:
                lines += ["", "**Clamp warnings:**", *[f"- {w}" for w in warnings]]
        else:
            lines.append("(no config change — KEEP_AS_IS / recommendation only)")
        lines += ["", "## Risks", "", self.risks or "(none noted)", ""]
        lines += [
            "---",
            "*Dry-run: esta propuesta NO está activa. Requiere aprobación humana para promoverse a `status=active`.*",
        ]
        return "\n".join(lines)
