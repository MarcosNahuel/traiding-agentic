"""Tests for the strategist approval flow: promote a pending_approval config to active,
or reject it. This is what closes the loop (Claude proposes → human confirms → bot adapts).
"""

from unittest.mock import MagicMock


def _supabase_with_pending(pending_row):
    sb = MagicMock()
    resp = MagicMock()
    resp.data = [pending_row] if pending_row else []
    (sb.table.return_value.select.return_value.eq.return_value
        .order.return_value.limit.return_value.execute.return_value) = resp
    return sb


def test_promote_sets_pending_to_active_and_supersedes():
    from app.services.strategist.approval import promote_latest_pending

    sb = _supabase_with_pending({"id": "cfg-1", "buy_adx_min": 25.0, "status": "pending_approval"})
    out = promote_latest_pending(sb)

    assert out is not None and out["id"] == "cfg-1"
    # at least two updates: supersede active + promote the pending one
    statuses = [
        c.args[0].get("status")
        for c in sb.table.return_value.update.call_args_list
        if c.args and isinstance(c.args[0], dict) and "status" in c.args[0]
    ]
    assert "superseded" in statuses   # old active deactivated
    assert "active" in statuses       # pending promoted


def test_promote_returns_none_when_nothing_pending():
    from app.services.strategist.approval import promote_latest_pending

    sb = _supabase_with_pending(None)
    assert promote_latest_pending(sb) is None
    sb.table.return_value.update.assert_not_called()


def test_reject_marks_pending_rejected_without_touching_active():
    from app.services.strategist.approval import reject_latest_pending

    sb = _supabase_with_pending({"id": "cfg-9", "status": "pending_approval"})
    out = reject_latest_pending(sb)

    assert out is not None and out["id"] == "cfg-9"
    payload = sb.table.return_value.update.call_args.args[0]
    assert payload["status"] == "rejected"
    # reject must NEVER promote/supersede an active config
    statuses = [
        c.args[0].get("status")
        for c in sb.table.return_value.update.call_args_list
        if c.args and isinstance(c.args[0], dict) and "status" in c.args[0]
    ]
    assert "active" not in statuses
    assert "superseded" not in statuses
