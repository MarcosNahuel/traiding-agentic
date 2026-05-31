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


def test_write_report_event_persists_full_report():
    """El informe diario de Claude se guarda en risk_events (lo lee el dashboard)."""
    from app.services.strategist.outputs import write_report_event

    sb = MagicMock()
    d = StrategistDecision(
        decision="RECOMMEND_PAUSE", confidence=0.9, summary="pausa por chop",
        evidence=["PF 0.31", "F&G 28"], risks="falso positivo",
        performance_review="PF 30d 0.31", macro_context="F&G 28 cayendo",
    )
    write_report_event(sb, d, run_at_iso="2026-05-31T06:00:00Z")

    sb.table.assert_any_call("risk_events")
    payload = sb.table.return_value.insert.call_args.args[0]
    assert payload["event_type"] == "strategist_report"
    assert payload["details"]["decision"] == "RECOMMEND_PAUSE"
    assert payload["details"]["macro_context"] == "F&G 28 cayendo"
    assert payload["details"]["confidence"] == 0.9
    assert "pausa por chop" in payload["message"]


def test_insert_returns_none_on_db_failure():
    """F5 (jury): si el insert falla, NO reportar éxito (return None) — evita Telegram fantasma."""
    from app.services.strategist.outputs import insert_pending_config

    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.side_effect = Exception("constraint violation")
    res = insert_pending_config(supabase, _tweak(), run_at_iso="2026-05-30T06:00:00Z")
    assert res is None


def test_insert_drops_arbitrary_keys_from_payload():
    """F2 (jury): claves arbitrarias nunca llegan al payload del insert."""
    from app.services.strategist.outputs import insert_pending_config

    supabase = MagicMock()
    d = StrategistDecision(
        decision="TWEAK_PARAMS", confidence=0.7, summary="x", evidence=["a", "b", "c"],
        proposed_config={"buy_adx_min": 25.0, "trading_enabled": True},
    )
    insert_pending_config(supabase, d, run_at_iso="2026-05-30T06:00:00Z")
    payload = supabase.table.return_value.insert.call_args.args[0]
    assert "trading_enabled" not in payload
    assert payload["buy_adx_min"] == 25.0


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
