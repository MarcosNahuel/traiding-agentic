"""TDD tests for exit_simulators V0–V3.

Synthesizes 1-minute klines for each scenario instead of relying on real
data. Each simulator must satisfy the invariants in spec §4.3.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.scripts.diagnostics.lib.exit_simulators import (  # noqa: E402
    Entry,
    simulate_v0_baseline,
    simulate_v1_partial_2atr,
    simulate_v2_partial_3atr,
    simulate_v3_no_partial_3atr,
)


# Fixture builders ---------------------------------------------------------

def _bars(prices: list[tuple[float, float, float, float]],  # OHLC
          start: datetime | None = None) -> pd.DataFrame:
    """Build a 1m kline DF from a list of OHLC tuples."""
    start = start or datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    rows = []
    for i, (o, h, l, c) in enumerate(prices):
        ot = start + timedelta(minutes=i)
        ct = ot + timedelta(minutes=1) - timedelta(milliseconds=1)
        rows.append(dict(
            open_time=pd.Timestamp(ot),
            close_time=pd.Timestamp(ct),
            open=o, high=h, low=l, close=c,
            volume=0.0, symbol="TEST", interval="1m",
        ))
    return pd.DataFrame(rows)


def _entry_long(price: float = 100.0, atr: float = 1.0) -> Entry:
    ts = datetime(2026, 4, 1, 11, 59, tzinfo=timezone.utc)  # 1 min before bars
    return Entry("TEST", "long", pd.Timestamp(ts), price, atr)


def _entry_short(price: float = 100.0, atr: float = 1.0) -> Entry:
    ts = datetime(2026, 4, 1, 11, 59, tzinfo=timezone.utc)
    return Entry("TEST", "short", pd.Timestamp(ts), price, atr)


# V0 baseline --------------------------------------------------------------

class TestV0Baseline:
    def test_long_hits_tp(self):
        # entry 100, atr 1, sl_k=2 → SL=98, tp_k=3 → TP=103
        bars = _bars([(100, 102, 99, 101), (101, 103.5, 100, 103)])
        r = simulate_v0_baseline(_entry_long(), bars, sl_k=2.0, tp_k=3.0,
                                  fee_bps=0, slip_bps=0)
        assert r.exit_reason == "TP"
        assert r.touched_1r is True
        assert r.pnl_r == pytest.approx(1.5)  # TP at +3 / 1R=2 = 1.5R

    def test_long_hits_sl(self):
        bars = _bars([(100, 100.5, 97.5, 98)])  # low=97.5 < SL=98
        r = simulate_v0_baseline(_entry_long(), bars, sl_k=2.0, tp_k=3.0,
                                  fee_bps=0, slip_bps=0)
        assert r.exit_reason == "SL"
        assert r.pnl_r == pytest.approx(-1.0)
        assert r.touched_1r is False

    def test_long_touches_1r_then_sl(self):
        # First bar high reaches +1R (high=102), then second bar drops to SL
        bars = _bars([(100, 102, 99, 101), (101, 101, 97, 98)])
        r = simulate_v0_baseline(_entry_long(), bars, sl_k=2.0, tp_k=3.0,
                                  fee_bps=0, slip_bps=0)
        assert r.exit_reason == "SL"
        assert r.touched_1r is True
        assert r.pnl_r == pytest.approx(-1.0)

    def test_short_symmetric_tp(self):
        # entry 100, sl=102, tp=97 (3 atrs down)
        bars = _bars([(100, 100, 98, 99), (99, 99.5, 96.5, 97)])
        r = simulate_v0_baseline(_entry_short(), bars, sl_k=2.0, tp_k=3.0,
                                  fee_bps=0, slip_bps=0)
        assert r.exit_reason == "TP"
        assert r.pnl_r == pytest.approx(1.5)

    def test_atr_zero_raises(self):
        e = _entry_long(atr=0)
        with pytest.raises(ValueError):
            simulate_v0_baseline(e, _bars([(100, 100, 100, 100)]),
                                  sl_k=2.0, tp_k=3.0)

    def test_end_of_data(self):
        bars = _bars([(100, 100.5, 99.5, 100.2)])  # never hits SL or TP
        r = simulate_v0_baseline(_entry_long(), bars, sl_k=2.0, tp_k=3.0,
                                  fee_bps=0, slip_bps=0)
        assert r.exit_reason == "END_OF_DATA"


# V1 / V2 partial + Chandelier --------------------------------------------

class TestV1V2PartialChandelier:
    def test_long_sl_before_partial(self):
        # SL hits first, partial never executed
        bars = _bars([(100, 100.5, 97.5, 98)])
        r = simulate_v1_partial_2atr(_entry_long(), bars, sl_k=2.0,
                                      fee_bps=0, slip_bps=0)
        assert r.exit_reason == "SL"
        assert r.pnl_r == pytest.approx(-1.0)

    def test_long_partial_then_chandelier_2atr(self):
        # Bar 1: hits +1R partial at 102. high=102, low=99. extreme=102.
        # Bar 2: high pushes to 103, extreme=103. trail=103-2=101.
        # Bar 3: low=100.5 < trail=101 → exit on runner.
        bars = _bars([
            (100, 102, 99, 101),
            (101, 103, 100.5, 102),
            (102, 102.5, 100.5, 100.6),
        ])
        r = simulate_v1_partial_2atr(_entry_long(), bars, sl_k=2.0,
                                      fee_bps=0, slip_bps=0)
        assert r.exit_reason == "PARTIAL_THEN_CHANDELIER"
        assert r.touched_1r is True
        # Partial leg: +1 quote per qty, runner: 101-100=+1 per qty (trail=101)
        # Both legs = 0.5*1 + 0.5*1 = 1 quote per total_qty;
        # 1R per qty (atr*sl_k=2). pnl_r = 1/2 = 0.5
        assert r.pnl_r == pytest.approx(0.5, abs=1e-6)

    def test_long_partial_3atr_wider_trail_runs_further(self):
        # Same trajectory, k=3 keeps the runner alive longer.
        bars = _bars([
            (100, 102, 99, 101),
            (101, 103, 100.5, 102),
            (102, 102.5, 100.5, 100.6),
            (100.6, 100.6, 99.6, 99.7),  # k=3: trail=103-3=100, low=99.6 hits
        ])
        r = simulate_v2_partial_3atr(_entry_long(), bars, sl_k=2.0,
                                      fee_bps=0, slip_bps=0)
        assert r.exit_reason == "PARTIAL_THEN_CHANDELIER"
        # Partial @+1 (+1 per qty), runner @100 (= breakeven, 0 per qty)
        # total = 0.5*1 + 0.5*0 = 0.5 quote per total_qty; 1R=2 → 0.25R
        assert r.pnl_r == pytest.approx(0.25, abs=1e-6)

    def test_short_partial(self):
        # entry short 100, atr=1, sl_k=2 → SL=102, partial @ 98
        # Bar 1: low=98, high=100.5 → partial taken. extreme=98.
        # Bar 2: low=97 (extreme=97), trail=97+2=99. high=98.5 < 99: still alive.
        # Bar 3: high=99.5 >= trail=99 → exit.
        bars = _bars([
            (100, 100.5, 98, 99),
            (99, 99.2, 97, 97.5),
            (97.5, 99.5, 97.5, 99),
        ])
        r = simulate_v1_partial_2atr(_entry_short(), bars, sl_k=2.0,
                                      fee_bps=0, slip_bps=0)
        assert r.exit_reason == "PARTIAL_THEN_CHANDELIER"

    def test_partial_runner_runs_to_eod(self):
        # Partial taken at 101, k=2 trail=100. Low stays above trail → EOD.
        bars = _bars([(100, 102, 100.5, 101)])
        r = simulate_v1_partial_2atr(_entry_long(), bars, sl_k=2.0,
                                      fee_bps=0, slip_bps=0)
        assert r.exit_reason == "PARTIAL_THEN_END"


# V3 no-partial + Chandelier 3 ---------------------------------------------

class TestV3NoPartial3ATR:
    def test_long_chandelier_protects_profit(self):
        # entry 100, atr=1, sl=98 (sl_k=2), trail=high-3
        # Bar1 high=104 (extreme), trail=101. low=100 OK.
        # Bar2 low=100.5 < trail=101 → CHANDELIER exit at 101.
        bars = _bars([
            (100, 104, 100, 103),
            (103, 103, 100.5, 101),
        ])
        r = simulate_v3_no_partial_3atr(_entry_long(), bars, sl_k=2.0,
                                         fee_bps=0, slip_bps=0)
        assert r.exit_reason == "CHANDELIER"
        # exit at 101, pnl=1, r=2 → 0.5R
        assert r.pnl_r == pytest.approx(0.5, abs=1e-6)

    def test_long_initial_sl_when_trail_below(self):
        # Bar1 modest high=100.5, trail=97.5 < initial SL=98 → effective stop=98
        bars = _bars([(100, 100.5, 97.5, 98)])
        r = simulate_v3_no_partial_3atr(_entry_long(), bars, sl_k=2.0,
                                         fee_bps=0, slip_bps=0)
        assert r.exit_reason == "SL"
        assert r.pnl_r == pytest.approx(-1.0)

    def test_short_chandelier(self):
        bars = _bars([
            (100, 100, 96, 97),  # extreme=96, trail=99
            (97, 99.5, 96.5, 99),  # high=99.5 >= 99 → CHANDELIER
        ])
        r = simulate_v3_no_partial_3atr(_entry_short(), bars, sl_k=2.0,
                                         fee_bps=0, slip_bps=0)
        assert r.exit_reason == "CHANDELIER"

    def test_end_of_data(self):
        bars = _bars([(100, 100.5, 99.5, 100.1)])
        r = simulate_v3_no_partial_3atr(_entry_long(), bars, sl_k=2.0,
                                         fee_bps=0, slip_bps=0)
        assert r.exit_reason == "END_OF_DATA"
