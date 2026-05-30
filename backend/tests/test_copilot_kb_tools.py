"""Unit tests for the co-pilot's pure RAG/tool logic (app.services.copilot.kb_tools).

No claude_agent_sdk import here — these are the SDK-free impls behind the @tool wrappers.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def kb(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge-base"
    (root / "strategies").mkdir(parents=True)
    (root / "market-regimes").mkdir(parents=True)
    (root / "decision-matrix.md").write_text(
        "# Decision Matrix\nEn regimen ranging sin breakout confirmado, NO entrar.\n",
        encoding="utf-8",
    )
    (root / "strategies" / "01-trend-momentum.md").write_text(
        "# Trend Momentum\nRequiere ADX>20 y tendencia clara.\n", encoding="utf-8"
    )
    (root / "market-regimes" / "ranging-high-vol.md").write_text(
        "# Ranging High Vol\nChop peligroso, esperar breakout.\n", encoding="utf-8"
    )
    return root


def test_read_kb_returns_content(kb):
    from app.services.copilot.kb_tools import read_kb_impl
    out = read_kb_impl("decision-matrix.md", kb_root=kb)
    assert out["ok"] is True
    assert "NO entrar" in out["content"]


def test_read_kb_blocks_path_traversal(kb):
    """Must never read outside the KB root."""
    from app.services.copilot.kb_tools import read_kb_impl
    out = read_kb_impl("../../../../etc/passwd", kb_root=kb)
    assert out["ok"] is False
    assert "content" not in out


def test_read_kb_missing_file(kb):
    from app.services.copilot.kb_tools import read_kb_impl
    out = read_kb_impl("does-not-exist.md", kb_root=kb)
    assert out["ok"] is False


def test_search_kb_finds_matches(kb):
    from app.services.copilot.kb_tools import search_kb_impl
    out = search_kb_impl("breakout", kb_root=kb)
    assert out["ok"] is True
    paths = {r["path"].replace("\\", "/") for r in out["results"]}
    assert "decision-matrix.md" in paths
    assert "market-regimes/ranging-high-vol.md" in paths
    assert "strategies/01-trend-momentum.md" not in paths  # no 'breakout' there


def test_search_kb_case_insensitive(kb):
    from app.services.copilot.kb_tools import search_kb_impl
    out = search_kb_impl("CHOP", kb_root=kb)
    assert any("ranging-high-vol" in r["path"].replace("\\", "/") for r in out["results"])


def test_get_recent_trades_reads_closed_positions():
    from app.services.copilot.kb_tools import get_recent_trades_impl
    supabase = MagicMock()
    rows = MagicMock()
    rows.data = [
        {"symbol": "ETHUSDT", "realized_pnl": -1.4, "closed_at": "2026-05-29T10:00:00Z"},
        {"symbol": "ETHUSDT", "realized_pnl": 2.1, "closed_at": "2026-05-28T10:00:00Z"},
    ]
    (supabase.table.return_value.select.return_value.eq.return_value.eq.return_value
        .order.return_value.limit.return_value.execute.return_value) = rows

    out = get_recent_trades_impl("ETHUSDT", 5, supabase=supabase)
    assert out["ok"] is True
    assert out["count"] == 2
    assert out["trades"][0]["realized_pnl"] == -1.4
