# -*- coding: utf-8 -*-
"""Validacion out-of-sample del edge donchian-bull (ETH-only).

El lab.py original reporta half_a/half_b del MISMO periodo de seleccion: no es OOS.
Este modulo agrega las tres piezas que faltan para decidir si el PF ~1.30 es edge
real o artefacto de overfitting (seleccion entre ~28 variantes sin correccion):

  1. WALK-FORWARD ANCLADO. Train expansivo + test rodante. En cada fold se elige
     la mejor variante SOLO con datos de train y se la evalua intacta en el test
     siguiente. Las trades OOS concatenadas = "lo que habrias ganado de verdad".
     Tambien se reporta la donchian_bull FIJA por fold (decae con el tiempo?).

  2. DEFLATED / PROBABILISTIC SHARPE (Bailey & Lopez de Prado 2014). Corrige el
     Sharpe observado por: numero de trials probados (~N variantes), skew, kurtosis
     y largo de muestra. DSR = P(Sharpe_real > Sharpe_esperado_por_azar_entre_N_trials).
     Si DSR < 0.95 el "edge" no sobrevive el multiple testing.

  3. HOLD-OUT POR REGIMEN. La donchian_bull FIJA evaluada por anio calendario y en
     el bear secular 2022 (que el backtest de 24m nunca vio). Separa alpha de
     breakout de beta-timing "crypto subio y estuvimos long".

Uso:  python scripts/backtest-lab/oos_validate.py [--months 60] [--symbol ETHUSDT]
      (la primera corrida descarga ~5 anios de klines 1h y computa indicadores;
       cachea el parquet enriquecido, las siguientes son rapidas)
"""

import argparse
import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

import lab  # mismo dir: reutiliza motor (simulate, metrics, indicadores, variantes)

OUT_DIR = lab.OUT_DIR
GAMMA_EM = 0.5772156649015329  # Euler-Mascheroni
N = NormalDist()


# ───────────────────────── datos (historia extendida) ─────────────────────────

def build_enriched(symbol: str, months: int) -> pd.DataFrame:
    """Descarga/cachea klines 1h + indicadores sobre una ventana larga."""
    enr_f = OUT_DIR / f"enriched_{symbol}_1h_{months}m_oos.parquet"
    # reusar cache propio o el del lab (enriched_<sym>_1h_<months>m.parquet) si existe
    for cand in (enr_f, OUT_DIR / f"enriched_{symbol}_1h_{months}m.parquet"):
        if cand.exists():
            df = pd.read_parquet(cand)
            if "bull600" not in df.columns:
                sma600 = df["close"].rolling(600).mean()
                df["bull600"] = (df["close"] > sma600) & (sma600 > sma600.shift(24))
            print(f"[{symbol}] enriquecido cacheado ({cand.name}): {len(df)} velas "
                  f"({df['ts'].iloc[0].date()} -> {df['ts'].iloc[-1].date()})")
            return df
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=int(30.4 * months))
    print(f"[{symbol}] descargando klines 1h desde {start.date()} (~{months}m)...")
    df = lab.fetch_klines(symbol, "1h", int(start.timestamp() * 1000),
                          int(end.timestamp() * 1000))
    print(f"[{symbol}] {len(df)} velas. computando indicadores (entropy+hurst rodantes, "
          f"esto tarda varios minutos en {months}m)...")
    df = lab.compute_indicators(df)
    df["entropy"] = lab.entropy_ratio_series(df["close"].values)
    df["hurst"] = lab.hurst_series(df["close"].values)
    # columna bull600 (config prod) por completitud
    sma600 = df["close"].rolling(600).mean()
    df["bull600"] = (df["close"] > sma600) & (sma600 > sma600.shift(24))
    df.to_parquet(enr_f)
    print(f"[{symbol}] enriquecido guardado en {enr_f.name}")
    return df


# ───────────────────────── sharpe deflactado ─────────────────────────

def per_trade_returns(trades: list[dict], notional: float) -> np.ndarray:
    if not trades:
        return np.array([])
    return np.array([t["pnl"] / notional for t in trades], dtype=float)


def obs_sharpe(r: np.ndarray) -> float:
    """Sharpe por-trade NO anualizado (mean/std). Base para PSR/DSR."""
    if len(r) < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1))


def psr(sr_obs: float, n: int, skew: float, kurt: float, sr_benchmark: float = 0.0) -> float:
    """Probabilistic Sharpe Ratio: P(SR_real > sr_benchmark).

    kurt = kurtosis NO-excess (normal => 3). Lopez de Prado eq. PSR.
    """
    if n < 2:
        return float("nan")
    denom = 1.0 - skew * sr_obs + (kurt - 1.0) / 4.0 * sr_obs ** 2
    if denom <= 0:
        return float("nan")
    z = (sr_obs - sr_benchmark) * math.sqrt(n - 1) / math.sqrt(denom)
    return float(N.cdf(z))


def expected_max_sharpe(var_sr_trials: float, n_trials: int) -> float:
    """E[max SR] esperado por azar entre n_trials independientes (Lopez de Prado).

    SR* = sqrt(Var(SR_trials)) * ((1-gamma)*Z(1-1/T) + gamma*Z(1-1/(T*e)))
    """
    if n_trials < 2 or var_sr_trials <= 0:
        return 0.0
    sd = math.sqrt(var_sr_trials)
    z1 = N.inv_cdf(1.0 - 1.0 / n_trials)
    z2 = N.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    return float(sd * ((1.0 - GAMMA_EM) * z1 + GAMMA_EM * z2))


def deflated_sharpe(target_r: np.ndarray, all_trial_sharpes: list[float], n_trials: int) -> dict:
    """DSR completo para una estrategia objetivo dada la batería de trials probados."""
    n = len(target_r)
    if n < 2:
        return {"n": n, "error": "muy pocas trades"}
    sr = obs_sharpe(target_r)
    # momentos
    s = pd.Series(target_r)
    skew = float(s.skew())
    kurt = float(s.kurt()) + 3.0  # pandas da excess kurtosis -> a no-excess
    # variabilidad del SR entre trials (selection variance)
    trial_sr = np.array([x for x in all_trial_sharpes if not math.isnan(x)])
    var_trials = float(trial_sr.var(ddof=1)) if len(trial_sr) > 1 else 0.0
    sr_star = expected_max_sharpe(var_trials, n_trials)
    return {
        "n_trades": n,
        "sharpe_obs_per_trade": round(sr, 4),
        "skew": round(skew, 3),
        "kurtosis": round(kurt, 3),
        "n_trials": n_trials,
        "var_sharpe_across_trials": round(var_trials, 5),
        "expected_max_sharpe_by_chance": round(sr_star, 4),
        "PSR_vs_0": round(psr(sr, n, skew, kurt, 0.0), 4),
        "DSR": round(psr(sr, n, skew, kurt, sr_star), 4),
    }


# ───────────────────────── walk-forward ─────────────────────────

def run_all_variants(df: pd.DataFrame, symbol: str) -> dict[str, list[dict]]:
    """Simula cada variante una vez sobre el df completo (indicadores con warmup correcto)."""
    out = {}
    for name, overrides in lab.variants().items():
        params = {**lab.BASE_PARAMS, **overrides}
        trades = lab.simulate(df, symbol, params)
        out[name] = trades
    return out


def trades_in_window(trades: list[dict], lo: str, hi: str) -> list[dict]:
    return [t for t in trades if lo <= t["entry_ts"] < hi]


def walk_forward(all_trades: dict[str, list[dict]], df: pd.DataFrame, symbol: str,
                 train_min_months: int, step_months: int, min_train_trades: int) -> dict:
    """Anclado: train=[t0, edge), test=[edge, edge+step). Selecciona en train, evalua en test."""
    ts0 = df["ts"].iloc[0]
    ts_end = df["ts"].iloc[-1]
    edge = ts0 + pd.DateOffset(months=train_min_months)
    folds = []
    oos_selected, oos_fixed = [], []
    fixed = "donchian_bull"
    while edge < ts_end:
        test_hi = edge + pd.DateOffset(months=step_months)
        lo_s, edge_s, hi_s = str(ts0), str(edge), str(min(test_hi, ts_end))
        # seleccion sobre train
        best, best_key = None, None
        for name, trs in all_trades.items():
            if name == "baseline":
                continue
            tr_train = trades_in_window(trs, lo_s, edge_s)
            m = lab.metrics(tr_train)
            if m["n"] < min_train_trades:
                continue
            key = (m["pf"] if math.isfinite(m["pf"]) else 9.99, m["expectancy"])
            if best is None or key > best_key:
                best, best_key, best_name = m, key, name
        # evaluacion OOS de la seleccionada
        sel_name = best_name if best is not None else fixed
        sel_test = trades_in_window(all_trades[sel_name], edge_s, hi_s)
        fix_test = trades_in_window(all_trades[fixed], edge_s, hi_s)
        oos_selected.extend(sel_test)
        oos_fixed.extend(fix_test)
        folds.append({
            "train_end": edge.date().isoformat(),
            "test_end": min(test_hi, ts_end).date().isoformat(),
            "selected_variant": sel_name,
            "selected_oos": lab.metrics(sel_test),
            "fixed_donchian_bull_oos": lab.metrics(fix_test),
        })
        edge = test_hi
    return {
        "folds": folds,
        "oos_selected_aggregate": lab.metrics(oos_selected),
        "oos_fixed_donchian_bull_aggregate": lab.metrics(oos_fixed),
        "selection_stability": _stability(folds, fixed),
    }


def _stability(folds: list[dict], fixed: str) -> dict:
    picks = [f["selected_variant"] for f in folds]
    return {
        "n_folds": len(folds),
        "times_picked_donchian_bull": picks.count(fixed),
        "distinct_variants_picked": len(set(picks)),
        "picks": picks,
    }


# ───────────────────────── breakdown por regimen / anio ─────────────────────────

def yearly_breakdown(trades: list[dict]) -> dict:
    out = {}
    for y in sorted({t["entry_ts"][:4] for t in trades}):
        out[y] = lab.metrics([t for t in trades if t["entry_ts"][:4] == y])
    return out


def window_metrics(trades: list[dict], lo: str, hi: str, label: str) -> dict:
    m = lab.metrics([t for t in trades if lo <= t["entry_ts"] < hi])
    m["window"] = f"{label} [{lo[:10]}..{hi[:10]})"
    return m


# ───────────────────────── main ─────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=60)
    ap.add_argument("--symbol", default="ETHUSDT")
    ap.add_argument("--train-min-months", type=int, default=12)
    ap.add_argument("--step-months", type=int, default=6)
    ap.add_argument("--min-train-trades", type=int, default=12)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sym = args.symbol
    notional = lab.NOTIONAL.get(sym, 60.0)

    df = build_enriched(sym, args.months)
    print(f"\n[{sym}] simulando {len(lab.variants())} variantes sobre {len(df)} velas...")
    all_trades = run_all_variants(df, sym)

    don = all_trades["donchian_bull"]
    print(f"[{sym}] donchian_bull: {len(don)} trades en {args.months}m "
          f"({df['ts'].iloc[0].date()} -> {df['ts'].iloc[-1].date()})")

    # 1. walk-forward
    wf = walk_forward(all_trades, df, sym, args.train_min_months,
                      args.step_months, args.min_train_trades)

    # 2. deflated sharpe (trials = todas las variantes ejecutadas)
    trial_sharpes = [obs_sharpe(per_trade_returns(t, notional)) for t in all_trades.values()]
    dsr = deflated_sharpe(per_trade_returns(don, notional), trial_sharpes, len(all_trades))

    # 3. breakdown anual + bear 2022
    full = lab.metrics(don)
    by_year = yearly_breakdown(don)
    bear22 = window_metrics(don, "2021-11-01", "2023-01-01", "bear_2021H2_2022")
    bull2425 = window_metrics(don, "2023-10-01", "2026-12-31", "bull_2023H2_2025")

    report = {
        "symbol": sym, "months": args.months,
        "data_range": [str(df["ts"].iloc[0]), str(df["ts"].iloc[-1])],
        "full_period_donchian_bull": full,
        "deflated_sharpe": dsr,
        "walk_forward": wf,
        "by_year_donchian_bull": by_year,
        "regime_holdout": {"bear": bear22, "bull": bull2425},
    }

    # ── reporte consola ──
    print("\n" + "=" * 78)
    print(f"VALIDACION OOS — {sym} — donchian_bull")
    print("=" * 78)
    print(f"\nFull period (in-sample, todas las trades):")
    print(f"  n={full['n']} WR={full['wr']}% PF={full['pf']} exp=${full['expectancy']} "
          f"PnL=${full['pnl']} DD=${full['max_dd']}")

    print(f"\n[1] WALK-FORWARD ANCLADO (train>={args.train_min_months}m, test={args.step_months}m):")
    print(f"    {'train_end':<12}{'test_end':<12}{'elegida':<22}{'OOS n/PF/PnL':<22}{'don_bull OOS'}")
    for f in wf["folds"]:
        s, x = f["selected_oos"], f["fixed_donchian_bull_oos"]
        print(f"    {f['train_end']:<12}{f['test_end']:<12}{f['selected_variant']:<22}"
              f"n{s['n']}/PF{s['pf']}/${s['pnl']:<8}  n{x['n']}/PF{x['pf']}/${x['pnl']}")
    agg_s = wf["oos_selected_aggregate"]
    agg_f = wf["oos_fixed_donchian_bull_aggregate"]
    print(f"  OOS agregado (seleccion walk-fwd): n={agg_s['n']} WR={agg_s['wr']}% "
          f"PF={agg_s['pf']} exp=${agg_s['expectancy']} PnL=${agg_s['pnl']}")
    print(f"  OOS agregado (donchian_bull fija): n={agg_f['n']} WR={agg_f['wr']}% "
          f"PF={agg_f['pf']} exp=${agg_f['expectancy']} PnL=${agg_f['pnl']}")
    st = wf["selection_stability"]
    print(f"  estabilidad: donchian_bull elegida {st['times_picked_donchian_bull']}/{st['n_folds']} folds; "
          f"{st['distinct_variants_picked']} variantes distintas elegidas")

    print(f"\n[2] DEFLATED SHARPE (correccion por {dsr.get('n_trials')} trials):")
    print(f"    Sharpe/trade={dsr.get('sharpe_obs_per_trade')} skew={dsr.get('skew')} "
          f"kurt={dsr.get('kurtosis')}")
    print(f"    E[max Sharpe por azar]={dsr.get('expected_max_sharpe_by_chance')}")
    print(f"    PSR vs 0  = {dsr.get('PSR_vs_0')}   (P de que Sharpe_real>0)")
    print(f"    DSR       = {dsr.get('DSR')}   (P de Sharpe_real > esperado-por-azar)")
    veredicto = "EDGE SOBREVIVE" if (dsr.get('DSR') or 0) >= 0.95 else "NO SOBREVIVE multiple-testing"
    print(f"    => {veredicto}")

    print(f"\n[3] HOLD-OUT POR REGIMEN (donchian_bull fija):")
    for y, m in by_year.items():
        print(f"    {y}: n={m['n']:>3} WR={m['wr']:>5}% PF={m['pf']:>6} PnL=${m['pnl']:>8}")
    print(f"    bear 2021H2-2022: n={bear22['n']} PF={bear22['pf']} PnL=${bear22['pnl']}")
    print(f"    bull 2023H2-2025: n={bull2425['n']} PF={bull2425['pf']} PnL=${bull2425['pnl']}")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    out_f = OUT_DIR / f"oos_validation_{sym}_{stamp}.json"
    out_f.write_text(json.dumps(report, indent=1, default=str))
    print(f"\nReporte guardado en {out_f}")


if __name__ == "__main__":
    main()
