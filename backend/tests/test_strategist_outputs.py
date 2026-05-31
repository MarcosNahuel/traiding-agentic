"""Tests for strategist outputs — the dry-run safety guarantee is the critical one:
the agent may ONLY insert status='pending_approval'; it must NEVER write status='active'
nor supersede the live config. A human promotes via approval.
"""

from unittest.mock import MagicMock

from app.services.strategist.schemas import StrategistDecision


def _tweak():
    return StrategistDecision(
        decision="TWEAK_PARAMS",
        confidence=0.7,
        summary="tighten ADX in chop",
        evidence=["a", "b", "c"],
        proposed_config={"buy_adx_min": 25.0},
    )


def test_write_evaluation_creates_dated_file(tmp_path):
    from app.services.strategist.outputs import write_evaluation

    d = StrategistDecision(decision="KEEP_AS_IS", confidence=0.6, summary="hold", evidence=[])
    path = write_evaluation(d, run_at_iso="2026-05-30T06:00:00Z", evaluations_dir=tmp_path)

    assert path.exists()
    assert path.name == "2026-05-30-strategist.md"
    body = path.read_text(encoding="utf-8")
    assert "KEEP_AS_IS" in body


def test_insert_pending_never_active_never_supersedes():
    from app.services.strategist.outputs import insert_pending_config

    supabase = MagicMock()
    insert_pending_config(supabase, _tweak(), run_at_iso="2026-05-30T06:00:00Z")

    # CRITICAL: never deactivate/supersede the live config
    supabase.table.return_value.update.assert_not_called()

    payload = supabase.table.return_value.insert.call_args.args[0]
    assert payload["status"] == "pending_approval"
    assert payload["status"] != "active"
    assert payload["proposed_by"] == "strategist"
    assert payload["buy_adx_min"] == 25.0


def test_insert_clamps_out_of_bounds_config():
    from app.services.strategist.outputs import insert_pending_config

    supabase = MagicMock()
    d = StrategistDecision(
        decision="TWEAK_PARAMS", confidence=0.7, summary="x", evidence=["a", "b", "c"],
        proposed_config={"buy_adx_min": 999.0},  # max bound is 40
    )
    insert_pending_config(supabase, d, run_at_iso="2026-05-30T06:00:00Z")

    payload = supabase.table.return_value.insert.call_args.args[0]
    assert payload["buy_adx_min"] == 40.0


def test_insert_skipped_for_keep_as_is():
    from app.services.strategist.outputs import insert_pending_config

    supabase = MagicMock()
    d = StrategistDecision(decision="KEEP_AS_IS", confidence=0.6, summary="hold", evidence=[])
    res = insert_pending_config(supabase, d, run_at_iso="2026-05-30T06:00:00Z")

    supabase.table.return_value.insert.assert_not_called()
    assert res is None


def test_insert_skipped_for_propose_strategy_change():
    """Structural recommendations live in the markdown only — no config row."""
    from app.services.strategist.outputs import insert_pending_config

    supabase = MagicMock()
    d = StrategistDecision(
        decision="PROPOSE_STRATEGY_CHANGE", confidence=0.8,
        summary="switch to mean-reversion in ranging", evidence=["a", "b", "c"],
        proposed_config={"buy_adx_min": 25.0},  # ignored — not a TWEAK
    )
    res = insert_pending_config(supabase, d, run_at_iso="2026-05-30T06:00:00Z")

    supabase.table.return_value.insert.assert_not_called()
    assert res is None
