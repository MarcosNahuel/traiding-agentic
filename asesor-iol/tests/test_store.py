from asesor_iol.state.store import Store


def test_pending_lifecycle(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    s.create_pending("abc", 1, {"simbolo": "SPY"}, 100.0)
    assert s.get_pending("abc")["status"] == "pending"
    s.resolve_pending("abc", "executed")
    assert s.get_pending("abc")["status"] == "executed"
    s.close()


def test_daily_amount_counts_only_executed(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    s.create_pending("a", 1, {}, 100.0)
    s.resolve_pending("a", "executed")
    s.create_pending("b", 1, {}, 50.0)
    s.resolve_pending("b", "cancelled")
    assert s.executed_amount_today() == 100.0
    s.close()


def test_committed_counts_pending_plus_executed(tmp_path):
    """F1 (jury): el tope diario debe contar pending + executed (no solo executed),
    para que dos órdenes concurrentes no superen el límite de dinero real."""
    s = Store(str(tmp_path / "s.db"))
    s.create_pending("a", 1, {}, 100.0)
    s.resolve_pending("a", "executed")
    s.create_pending("b", 1, {}, 50.0)            # pending (sin resolver)
    s.create_pending("c", 1, {}, 30.0)
    s.resolve_pending("c", "cancelled")            # no cuenta
    assert s.committed_amount_today() == 150.0     # 100 executed + 50 pending
    s.close()


def test_audit_writes(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    s.audit("test", "tool", {"x": 1}, {"ok": True})
    rows = s._conn.execute("SELECT COUNT(*) AS c FROM audit").fetchone()
    assert rows["c"] == 1
    s.close()
