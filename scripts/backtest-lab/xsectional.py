# -*- coding: utf-8 -*-
"""Cross-sectional momentum sobre cesta de alts (lead 2026-06-21).

El experimento ratio_rotation mostro que el edge (si existe) NO es mean-reversion
sino TREND RELATIVO, pero sobre 2 activos / 1 regimen no pasa DSR. La unica via con
n suficiente para que el trend-factor pase el filtro estadistico es CROSS-SECTIONAL
sobre una cesta amplia (Taming-The-Factor-Zoo / trend-factor crypto):

  - rankear N activos por momentum (retorno trailing),
  - rebalanceo semanal, long top-K (spot) y/o long-short top-vs-bottom (perps),
  - costos por turnover, walk-forward, Deflated Sharpe con n_trials honesto,
  - hold-out por regimen INCLUYENDO el bear 2021H2-2022.

Datos: 1d klines de data-api.binance.vision (publico, SIN geobloqueo, sin API key).
Universo FIJO definido por existencia temprana en Binance (mitiga survivorship, no lo
elimina: los alts que murieron no estan; los mainstream sobrevivieron).

NO toca produccion. Standalone (numpy+pandas+requests).

Uso:  python scripts/backtest-lab/xsectional.py [--download] [--start 2020-09-01]
"""

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd
import requests

OUT_DIR = Path(__file__).parent / "results"
DATA_DIR = OUT_DIR / "xsec"
VISION = "https://data-api.binance.vision/api/v3/klines"

FEE = 0.001
SLIPPAGE = 0.0005
COST_PER_LEG = FEE + SLIPPAGE  # 0.15% por ejecucion

# Universo: alts con cotizacion temprana en Binance (los que existian ~2020-2021).
UNIVERSE = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "SOLUSDT",
            "DOGEUSDT", "LTCUSDT", "LINKUSDT", "DOTUSDT", "AVAXUSDT", "MATICUSDT",
            "ATOMUSDT", "UNIUSDT", "BCHUSDT", "ETCUSDT", "XLMUSDT", "ALGOUSDT",
            "VETUSDT", "FILUSDT", "TRXUSDT", "EOSUSDT", "AAVEUSDT", "SANDUSDT"]

_ND = NormalDist()
_GAMMA = 0.5772156649015329


# ───────────────────────── Deflated Sharpe (mismo que ratio_rotation) ─────────────────────────

def obs_sharpe(r: np.ndarray) -> float:
    if len(r) < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1))


def _psr(sr, n, skew, kurt, sr_bench=0.0):
    if n < 2:
        return float("nan")
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2
    if denom <= 0:
        return float("nan")
    z = (sr - sr_bench) * math.sqrt(n - 1) / math.sqrt(denom)
    return float(_ND.cdf(z))


def _expected_max_sharpe(var_sr_trials, n_trials):
    if n_trials < 2 or var_sr_trials <= 0:
        return 0.0
    sd = math.sqrt(var_sr_trials)
    z1 = _ND.inv_cdf(1.0 - 1.0 / n_trials)
    z2 = _ND.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    return float(sd * ((1.0 - _GAMMA) * z1 + _GAMMA * z2))


def deflated_sharpe(target_r, all_trial_sharpes, n_trials):
    n = len(target_r)
    if n < 2:
        return {"n": n, "error": "muy pocas obs"}
    sr = obs_sharpe(target_r)
    s = pd.Series(target_r)
    skew = float(s.skew())
    kurt = float(s.kurt()) + 3.0
    trial_sr = np.array([x for x in all_trial_sharpes if not math.isnan(x)])
    var_trials = float(trial_sr.var(ddof=1)) if len(trial_sr) > 1 else 0.0
    sr_star = _expected_max_sharpe(var_trials, n_trials)
    return {
        "n_periods": n, "sharpe_obs_per_period": round(sr, 4),
        "skew": round(skew, 3), "kurtosis": round(kurt, 3), "n_trials": n_trials,
        "expected_max_sharpe_by_chance": round(sr_star, 4),
        "PSR_vs_0": round(_psr(sr, n, skew, kurt, 0.0), 4),
        "DSR": round(_psr(sr, n, skew, kurt, sr_star), 4),
    }


# ───────────────────────── descarga ─────────────────────────

def fetch_daily(symbol: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    rows, cur = [], start_ms
    while cur < end_ms:
        r = requests.get(VISION, params={"symbol": symbol, "interval": "1d",
                         "startTime": cur, "endTime": end_ms, "limit": 1000}, timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        cur = batch[-1][6] + 1
        if len(batch) < 1000:
            break
        time.sleep(0.1)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume",
                                     "close_time", "qv", "n", "tbv", "tbqv", "ig"])
    df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    return df.drop_duplicates("open_time")[["ts", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


def download_universe(start: str):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    start_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    cov = {}
    for sym in UNIVERSE:
        f = DATA_DIR / f"{sym}_1d.parquet"
        if f.exists():
            df = pd.read_parquet(f)
        else:
            df = fetch_daily(sym, start_ms, end_ms)
            if len(df):
                df.to_parquet(f)
        if len(df):
            cov[sym] = (str(df["ts"].iloc[0].date()), str(df["ts"].iloc[-1].date()), len(df))
            print(f"  {sym:<11} {cov[sym][0]} -> {cov[sym][1]}  ({cov[sym][2]} dias)")
        else:
            print(f"  {sym:<11} SIN DATOS")
    return cov


def load_panel():
    """Devuelve (close, dvol): paneles index=fecha, cols=simbolo.
    dvol = close*volume (dolar-volumen, proxy de liquidez)."""
    close, dvol = {}, {}
    for sym in UNIVERSE:
        f = DATA_DIR / f"{sym}_1d.parquet"
        if f.exists():
            df = pd.read_parquet(f).set_index("ts")
            close[sym] = df["close"]
            dvol[sym] = df["close"] * df["volume"]
    return pd.DataFrame(close).sort_index(), pd.DataFrame(dvol).sort_index()


# ───────────────────────── backtest cross-sectional ─────────────────────────

def backtest_xsec(close: pd.DataFrame, hold: int, lookback: int, k: int, long_short: bool,
                  dvol: pd.DataFrame = None, min_dvol: float = 5e6, liq_win: int = 30,
                  start: str = None, end: str = None) -> dict:
    """Momentum cross-sectional con EJECUCION REALISTA (lag-1) y FILTRO DE LIQUIDEZ.
    Señal de momentum en t (close), se ejecuta en t+1, retorno t+1 -> t+1+hold (sin lookahead).
    Filtro: solo activos con dolar-volumen medio (ult. liq_win dias, hasta t) >= min_dvol.
    long top-k (y short bottom-k si long_short). Pesos iguales. Costos por turnover."""
    px = close.copy()
    dv = dvol.copy() if dvol is not None else None
    if start:
        px = px[px.index >= pd.Timestamp(start, tz="UTC")]
        if dv is not None:
            dv = dv[dv.index >= pd.Timestamp(start, tz="UTC")]
    if end:
        px = px[px.index < pd.Timestamp(end, tz="UTC")]
        if dv is not None:
            dv = dv[dv.index < pd.Timestamp(end, tz="UTC")]
    dates = px.index
    period_rets, period_ts = [], []
    prev_w = pd.Series(0.0, index=px.columns)

    i = lookback
    while i + hold + 1 < len(dates):   # +1: ejecucion en t+1 (lag-1, no en el close que rankea)
        past = px.iloc[i - lookback]
        now = px.iloc[i]
        mom = (now / past - 1)
        valid = mom[past.notna() & now.notna() & px.iloc[i + 1].notna()].dropna()
        # filtro de liquidez con lag (solo info hasta t): ADV de los ult. liq_win dias
        if dv is not None and len(valid):
            adv = dv.iloc[max(0, i - liq_win):i].mean()
            liquid = adv[adv >= min_dvol].index
            valid = valid[valid.index.isin(liquid)]
        need = 2 * k if long_short else k
        if len(valid) < need:
            i += hold
            continue
        ranked = valid.sort_values(ascending=False)
        w = pd.Series(0.0, index=px.columns)
        w[ranked.index[:k]] = 1.0 / k
        if long_short:
            w[ranked.index[-k:]] = -1.0 / k
        # retorno del holding: entra en t+1, sale en t+1+hold (ejecucion realista)
        fwd = (px.iloc[i + 1 + hold] / px.iloc[i + 1] - 1)
        gross = float((w * fwd.reindex(w.index)).fillna(0.0).sum())
        turnover = float((w - prev_w).abs().sum())
        period_rets.append(gross - turnover * COST_PER_LEG)
        period_ts.append(str(dates[i].date()))
        prev_w = w
        i += hold

    r = np.array(period_rets)
    if len(r) == 0:
        return {"n": 0, "ann_ret": 0, "sharpe_ann": 0, "pf": 0, "maxdd": 0, "total_ret": 0, "rets": [], "ts": []}
    eq = np.cumprod(1 + r)
    peak = np.maximum.accumulate(eq)
    dd = float((((peak - eq) / peak)).max()) if len(eq) else 0   # drawdown vs pico CONTEMPORANEO
    periods_per_year = 365.0 / hold
    ann_ret = float(eq[-1] ** (periods_per_year / len(r)) - 1) if eq[-1] > 0 else -1.0
    sharpe_ann = float(r.mean() / r.std(ddof=1) * math.sqrt(periods_per_year)) if r.std(ddof=1) > 0 else 0.0
    wins, losses = r[r > 0], r[r <= 0]
    pf = float(wins.sum() / abs(losses.sum())) if losses.sum() != 0 else float("inf")
    return {"n": len(r), "ann_ret": round(ann_ret, 4), "sharpe_ann": round(sharpe_ann, 3),
            "pf": round(pf, 3), "maxdd": round(dd, 4), "total_ret": round(float(eq[-1] - 1), 4),
            "rets": period_rets, "ts": period_ts}


def by_year(res: dict) -> dict:
    out = {}
    for t, r in zip(res["ts"], res["rets"]):
        y = t[:4]
        out.setdefault(y, []).append(r)
    return {y: {"n": len(rs), "ret": round(float(np.prod([1 + x for x in rs]) - 1), 4)}
            for y, rs in sorted(out.items())}


# ───────────────────────── main ─────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--start", default="2020-09-01")
    args = ap.parse_args()

    if args.download:
        print("Descargando universo (1d, data.binance.vision):")
        download_universe(args.start)

    close, dvol = load_panel()
    if close.empty:
        print("Panel vacio. Corre con --download primero.")
        return
    print(f"\nPanel: {close.shape[1]} simbolos, {close.shape[0]} dias "
          f"({close.index[0].date()} -> {close.index[-1].date()})")
    alive = close.notna().sum(axis=1)
    print(f"Activos vivos: {int(alive.iloc[0])} al inicio -> {int(alive.iloc[-1])} al final")
    print(f"Ejecucion: lag-1 (entra t+1). Filtro liquidez: ADV>=$5M (ult 30d). Costos 0.15%/leg.")

    # grid de hiperparametros (lookback dias, hold dias, k activos, long_short)
    grid = []
    for lb in (30, 60, 90):
        for hold in (7, 14):
            for k in (3, 5):
                for ls in (False, True):
                    grid.append((lb, hold, k, ls))

    print(f"\n{'lookback/hold/k/ls':<24}{'n':>5}{'annRet%':>9}{'Sharpe':>8}{'PF':>7}{'maxDD%':>8}{'totRet%':>9}")
    results, trial_sharpes = {}, []
    best_lo, best_ls = None, None  # mejor por Sharpe en cada familia (sin filtro que oculte el DSR)
    for lb, hold, k, ls in grid:
        res = backtest_xsec(close, hold, lb, k, ls, dvol=dvol)
        if res["n"] < 10:
            continue
        key = f"lb{lb}/h{hold}/k{k}/{'LS' if ls else 'LO'}"
        results[key] = {kk: vv for kk, vv in res.items() if kk not in ("rets", "ts")}
        results[key]["by_year"] = by_year(res)
        trial_sharpes.append(obs_sharpe(np.array(res["rets"])))
        cand = (key, res["sharpe_ann"], res, lb, hold, k, ls)
        if ls and (best_ls is None or res["sharpe_ann"] > best_ls[1]):
            best_ls = cand
        if not ls and (best_lo is None or res["sharpe_ann"] > best_lo[1]):
            best_lo = cand
        print(f"{key:<24}{res['n']:>5}{res['ann_ret']*100:>9.1f}{res['sharpe_ann']:>8}{res['pf']:>7}"
              f"{res['maxdd']*100:>8.1f}{res['total_ret']*100:>9.1f}")

    out = {"meta": {"universe": list(close.columns),
                    "period": [str(close.index[0].date()), str(close.index[-1].date())],
                    "execution": "lag-1", "liquidity_filter": "ADV>=5e6/30d", "cost_per_leg": COST_PER_LEG},
           "grid": results, "evaluated": {}}

    def evaluate(tag, best):
        key, shp, res, lb, hold, k, ls = best
        print(f"\n{'='*80}\n=== MEJOR {tag}: {key} (Sharpe {shp}) ===")
        print("Por año:", {y: f"{m['ret']*100:.0f}%" for y, m in by_year(res).items()})
        bear = backtest_xsec(close, hold, lb, k, ls, dvol=dvol, start="2021-05-01", end="2023-01-01")
        bull = backtest_xsec(close, hold, lb, k, ls, dvol=dvol, start="2023-01-01", end="2026-01-01")
        print(f"  BEAR 2021-05..2022-12: n={bear['n']} totRet={bear['total_ret']*100:.1f}% "
              f"Sharpe={bear['sharpe_ann']} maxDD={bear['maxdd']*100:.1f}%")
        print(f"  BULL 2023-01..2025-12: n={bull['n']} totRet={bull['total_ret']*100:.1f}% Sharpe={bull['sharpe_ann']}")
        dsr = deflated_sharpe(np.array(res["rets"]), trial_sharpes, n_trials=len(trial_sharpes))
        print(f"  DSR: sharpe_obs/periodo={dsr['sharpe_obs_per_period']}  "
              f"E[max azar]={dsr['expected_max_sharpe_by_chance']}  PSR0={dsr['PSR_vs_0']}  *** DSR={dsr['DSR']} ***")
        bear_ok = bear["total_ret"] > 0
        passed = dsr["DSR"] >= 0.95 and bear_ok
        print(f"  GATE: DSR>=0.95 [{'OK' if dsr['DSR']>=0.95 else 'NO'}] + bear>0 [{'OK' if bear_ok else 'NO'}] "
              f"-> {'PASA' if passed else 'NO PASA'}")
        out["evaluated"][tag] = {
            "variant": key, "params": {"lookback": lb, "hold": hold, "k": k, "long_short": ls},
            "full": {kk: vv for kk, vv in res.items() if kk not in ("rets", "ts")},
            "by_year": by_year(res),
            "holdout": {"bear": {kk: vv for kk, vv in bear.items() if kk not in ("rets", "ts")},
                        "bull": {kk: vv for kk, vv in bull.items() if kk not in ("rets", "ts")}},
            "deflated_sharpe": dsr, "passed": passed}
        return passed

    p_lo = evaluate("LONG-ONLY (spot, mantiene beta)", best_lo) if best_lo else False
    p_ls = evaluate("LONG-SHORT (market-neutral, perps)", best_ls) if best_ls else False
    out["passed"] = bool(p_lo or p_ls)
    print(f"\n{'='*80}\nVEREDICTO GLOBAL: {'algun candidato PASA el gate' if out['passed'] else 'NINGUN candidato pasa DSR>=0.95 + bear hold-out>0 -> no implementar'}")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    out_f = OUT_DIR / f"xsectional_{stamp}.json"
    out_f.write_text(json.dumps(out, indent=1, default=str))
    print(f"\nGuardado en {out_f}")


if __name__ == "__main__":
    main()
