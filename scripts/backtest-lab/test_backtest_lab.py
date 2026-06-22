# -*- coding: utf-8 -*-
"""Tests de propiedad del backtest-lab (xsectional + ratio_rotation).

Verifican las invariantes que importan para confiar en un veredicto de edge:
  - Deflated Sharpe castiga el ruido y premia un edge genuino.
  - El backtest cross-sectional NO usa look-ahead (datos futuros no alteran el pasado).
  - El filtro de liquidez efectivamente excluye activos ilíquidos.
  - El half-life distingue mean-reversion de random walk.

Uso:  cd scripts/backtest-lab && python -m pytest test_backtest_lab.py -q
"""

import numpy as np
import pandas as pd
import pytest

import xsectional as xs
import ratio_rotation as rr


def _panel(prices: dict, start="2021-01-01", freq="1D"):
    idx = pd.date_range(start, periods=len(next(iter(prices.values()))), freq=freq, tz="UTC")
    return pd.DataFrame(prices, index=idx)


# ───────────────────────── Deflated Sharpe ─────────────────────────

def test_dsr_noise_is_low():
    """Ruido gaussiano sin edge, elegido entre 20 trials -> DSR debe ser bajo (<0.95)."""
    rng = np.random.default_rng(42)
    target = rng.normal(0.0, 0.02, 200)
    trials = [xs.obs_sharpe(rng.normal(0.0, 0.02, 200)) for _ in range(20)]
    d = xs.deflated_sharpe(target, trials, n_trials=20)
    assert d["DSR"] < 0.95


def test_dsr_strong_edge_is_high():
    """Edge genuino y fuerte (media muy positiva vs varianza) -> DSR alto."""
    rng = np.random.default_rng(0)
    target = rng.normal(0.03, 0.01, 300)        # sharpe/trade ~3, inequívoco
    trials = [xs.obs_sharpe(rng.normal(0.0, 0.01, 300)) for _ in range(10)]
    d = xs.deflated_sharpe(target, trials, n_trials=10)
    assert d["DSR"] > 0.95


# ───────────────────────── cross-sectional ─────────────────────────

def test_xsec_picks_winner():
    """LO k=1: con un activo en tendencia clara, el momentum lo elige y rinde > 0."""
    n = 120
    up = list(100 * (1.01 ** np.arange(n)))      # +1%/dia
    flat = [100.0] * n
    down = list(100 * (0.99 ** np.arange(n)))
    close = _panel({"UP": up, "FLAT": flat, "DOWN": down})
    res = xs.backtest_xsec(close, hold=7, lookback=14, k=1, long_short=False, dvol=None)
    assert res["n"] > 0
    assert res["total_ret"] > 0


def test_xsec_no_lookahead():
    """Alterar precios FUTUROS no debe cambiar los retornos de periodos anteriores."""
    rng = np.random.default_rng(7)
    n = 200
    data = {f"S{j}": list(100 * np.cumprod(1 + rng.normal(0, 0.02, n))) for j in range(6)}
    close = _panel(data)
    base = xs.backtest_xsec(close, hold=7, lookback=14, k=2, long_short=False, dvol=None)
    # romper los ultimos 20 dias con un shock enorme
    close2 = close.copy()
    close2.iloc[-20:] *= 5.0
    mod = xs.backtest_xsec(close2, hold=7, lookback=14, k=2, long_short=False, dvol=None)
    # los primeros retornos (muy anteriores al shock) deben ser identicos
    assert base["rets"][:5] == pytest.approx(mod["rets"][:5])


def test_liquidity_filter_excludes_illiquid():
    """Un activo con mejor momentum pero ilíquido (ADV < min) no debe entrar."""
    n = 80
    star = list(100 * (1.02 ** np.arange(n)))    # mejor momentum, pero lo haremos ilíquido
    ok = list(100 * (1.005 ** np.arange(n)))
    close = _panel({"ILIQUIDO": star, "LIQUIDO": ok})
    vol = _panel({"ILIQUIDO": [1.0] * n, "LIQUIDO": [1e6] * n})  # dvol iliquido<<5e6, liquido>=5e6
    dvol = close * vol
    res = xs.backtest_xsec(close, hold=7, lookback=14, k=1, long_short=False,
                           dvol=dvol, min_dvol=5e6, liq_win=10)
    # con k=1 y filtro, solo LIQUIDO califica -> rinde el +0.5%/dia, no el +2%
    assert res["n"] > 0
    assert res["total_ret"] < 5.0   # si hubiera tomado el iliquido (+2%/dia) el totRet seria gigante


# ───────────────────────── ratio_rotation ─────────────────────────

def test_half_life_distinguishes_regimes():
    """Random walk -> half-life enorme/inf; serie mean-reverting -> half-life finito y chico."""
    rng = np.random.default_rng(3)
    rw = np.cumsum(rng.normal(0, 1, 2000)) + 100      # random walk: no revierte
    # Ornstein-Uhlenbeck fuerte alrededor de 100
    ou = np.zeros(2000); ou[0] = 100
    for t in range(1, 2000):
        ou[t] = ou[t-1] + 0.3 * (100 - ou[t-1]) + rng.normal(0, 0.5)
    hl_rw = rr.half_life(rw)
    hl_ou = rr.half_life(ou)
    assert hl_ou < 50           # revierte rapido
    assert hl_rw > hl_ou * 3    # el random walk tarda mucho mas (o inf)


def test_ratio_meanrev_momentum_are_mirrors():
    """En el mismo panel, meanrev y momentum toman lados opuestos -> pnl agregado de signo opuesto
    (o ambos ~0). No pueden ganar los dos a la vez salvo por costos."""
    rng = np.random.default_rng(11)
    n = 1500
    btc = 100 * np.cumprod(1 + rng.normal(0, 0.01, n))
    eth = 100 * np.cumprod(1 + rng.normal(0.0003, 0.012, n))  # deriva relativa
    df = pd.DataFrame({"ts": pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"),
                       "open_btc": btc, "close_btc": btc, "open_eth": eth, "close_eth": eth})
    df["ratio"] = df["close_eth"] / df["close_btc"]
    mr = rr.simulate_spread(df, w=168, entry_z=1.5, exit_z=0.5, mode="meanrev")
    mo = rr.simulate_spread(df, w=168, entry_z=1.5, exit_z=0.5, mode="momentum")
    pnl_mr = sum(t["pnl"] for t in mr)
    pnl_mo = sum(t["pnl"] for t in mo)
    # no deben ser ambos fuertemente positivos (serian dinero gratis); al menos uno <= 0
    assert min(pnl_mr, pnl_mo) <= 0
