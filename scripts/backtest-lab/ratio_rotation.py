# -*- coding: utf-8 -*-
"""Experimento ratio-rotation BTC<->ETH (jury 2026-06-21).

Responde DOS preguntas con costo/riesgo cero, sobre los parquets 24m ya cacheados:

  1) ROTATION (long-only, ejecutable HOY en spot): siempre invertido en BTC o ETH
     segun el z-score del ratio ETH/BTC. ¿La rotacion por z-score le gana a holdear
     (BTC / ETH / 50-50)? 2 ejecuciones por trade.

  2) SPREAD (long/short, market-neutral simulado, requiere perps): long el barato /
     short el caro. ¿Hay edge en la reversion del spread, neto de costos? 4 ejecuciones
     por trade. Si esto NO es robusto, NO vale migrar a futuros.

Gate del jury: el edge real (no beta disfrazada) tiene que aparecer en el modo SPREAD y
sobrevivir a costos. La rotation long-only mantiene beta crypto -> en bear pierde igual.
El bear 2022 NO esta en estos datos (24m = 2024-06..2026-06); el breakdown por trimestre
es proxy parcial. Hold-out bear real = pendiente de descargar klines 2021-2022.

NO toca produccion. Standalone (numpy + pandas + pyarrow). No descarga nada.

Uso:  python scripts/backtest-lab/ratio_rotation.py
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

OUT_DIR = Path(__file__).parent / "results"
_ND = NormalDist()
_GAMMA = 0.5772156649015329  # Euler-Mascheroni


# ───── Deflated Sharpe (copia de oos_validate.py, standalone sin requests) ─────

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


def deflated_sharpe(target_r: np.ndarray, all_trial_sharpes: list, n_trials: int) -> dict:
    n = len(target_r)
    if n < 2:
        return {"n": n, "error": "muy pocas trades"}
    sr = obs_sharpe(target_r)
    s = pd.Series(target_r)
    skew = float(s.skew())
    kurt = float(s.kurt()) + 3.0
    trial_sr = np.array([x for x in all_trial_sharpes if not math.isnan(x)])
    var_trials = float(trial_sr.var(ddof=1)) if len(trial_sr) > 1 else 0.0
    sr_star = _expected_max_sharpe(var_trials, n_trials)
    return {
        "n_trades": n, "sharpe_obs_per_trade": round(sr, 4),
        "skew": round(skew, 3), "kurtosis": round(kurt, 3), "n_trials": n_trials,
        "expected_max_sharpe_by_chance": round(sr_star, 4),
        "PSR_vs_0": round(_psr(sr, n, skew, kurt, 0.0), 4),
        "DSR": round(_psr(sr, n, skew, kurt, sr_star), 4),
    }

FEE = 0.001        # 0.1% por lado (Binance spot) — mismo que lab.py
SLIPPAGE = 0.0005  # 0.05% por lado
COST_PER_LEG = FEE + SLIPPAGE  # 0.15% por ejecucion

NOTIONAL = 100.0   # por pata


# ───────────────────────── metricas (replica de lab.metrics) ─────────────────────────

def metrics(trades: list[dict]) -> dict:
    if not trades:
        return {"n": 0, "wr": 0, "pf": 0, "expectancy": 0, "pnl": 0, "max_dd": 0, "sharpe": 0}
    pnls = np.array([t["pnl"] for t in trades])
    wins, losses = pnls[pnls > 0], pnls[pnls <= 0]
    gross_w, gross_l = wins.sum(), abs(losses.sum())
    eq = np.cumsum(pnls)
    dd = float((np.maximum.accumulate(eq) - eq).max()) if len(eq) else 0.0
    return {
        "n": len(pnls),
        "wr": round(100 * len(wins) / len(pnls), 1),
        "pf": round(float(gross_w / gross_l), 3) if gross_l > 0 else float("inf"),
        "expectancy": round(float(pnls.mean()), 4),
        "pnl": round(float(pnls.sum()), 2),
        "max_dd": round(dd, 2),
        "sharpe": round(float(pnls.mean() / pnls.std() * math.sqrt(len(pnls))), 2) if pnls.std() > 0 else 0,
    }


def half_life(series: np.ndarray) -> float:
    """Half-life de reversion (Ornstein-Uhlenbeck): dr_t = a + b*r_{t-1}.
    half_life = -ln(2)/b si b<0 (revierte); inf si no revierte."""
    r = series[~np.isnan(series)]
    if len(r) < 50:
        return float("nan")
    lag = r[:-1]
    delta = np.diff(r)
    b = float(np.polyfit(lag, delta, 1)[0])
    if b >= 0:
        return float("inf")
    return float(-math.log(2) / b)


# ───────────────────────── carga + señal ─────────────────────────

def load_pair() -> pd.DataFrame:
    btc = pd.read_parquet(OUT_DIR / "klines_BTCUSDT_1h_24m.parquet")[["ts", "open", "close"]]
    eth = pd.read_parquet(OUT_DIR / "klines_ETHUSDT_1h_24m.parquet")[["ts", "open", "close"]]
    df = btc.merge(eth, on="ts", suffixes=("_btc", "_eth")).sort_values("ts").reset_index(drop=True)
    df["ratio"] = df["close_eth"] / df["close_btc"]
    return df


def zscore(ratio: pd.Series, w: int) -> pd.Series:
    mu = ratio.rolling(w, min_periods=w).mean()
    sd = ratio.rolling(w, min_periods=w).std(ddof=0)
    return (ratio - mu) / sd


# ───────────────────────── simuladores ─────────────────────────
# Señal en barra i (datos hasta i) -> ejecuta en open de i+1 (sin lookahead).

def simulate_rotation(df: pd.DataFrame, w: int, entry_z: float, mode: str = "meanrev") -> list[dict]:
    """Long-only: siempre en BTC o ETH. Flip binario con histeresis. 2 legs/trade.
    meanrev:  z>+entry -> BTC (ETH caro, ratio deberia bajar).  z<-entry -> ETH.
    momentum: z>+entry -> ETH (ratio subiendo, seguir al fuerte). z<-entry -> BTC."""
    z = zscore(df["ratio"], w).values
    o_btc, o_eth = df["open_btc"].values, df["open_eth"].values
    ts = df["ts"].values
    hi, lo = ("BTC", "ETH") if mode == "meanrev" else ("ETH", "BTC")
    trades, state, seg = [], None, None  # seg: (asset, entry_idx, entry_px)

    def close_seg(i_exec):
        a, i0, px0 = seg
        px1 = (o_btc if a == "BTC" else o_eth)[i_exec] * (1 - SLIPPAGE)
        px0s = px0 * (1 + SLIPPAGE)
        # slippage ya esta en los precios de fill -> el cost cobra solo FEE (no doble)
        pnl = NOTIONAL * (px1 / px0s - 1) - 2 * NOTIONAL * FEE
        trades.append({"entry_ts": str(ts[i0]), "exit_ts": str(ts[i_exec]), "asset": a,
                       "pnl": pnl, "ret_pct": round(100 * (px1 / px0s - 1), 3)})

    for i in range(w, len(df) - 1):
        if np.isnan(z[i]):
            continue
        want = state
        if z[i] > entry_z:
            want = hi
        elif z[i] < -entry_z:
            want = lo
        if want is None:
            continue
        if state is None:                      # primera entrada
            state = want
            seg = (state, i + 1, (o_btc if state == "BTC" else o_eth)[i + 1])
        elif want != state:                    # flip
            close_seg(i + 1)
            state = want
            seg = (state, i + 1, (o_btc if state == "BTC" else o_eth)[i + 1])
    if seg is not None:                        # cerrar al final
        close_seg(len(df) - 1)
    return trades


def simulate_spread(df: pd.DataFrame, w: int, entry_z: float, exit_z: float, mode: str = "meanrev") -> list[dict]:
    """Market-neutral (long/short, requiere perps). Entra cuando |z|>entry, sale a flat
    cuando |z|<exit. 4 legs por trade (2 patas x abrir+cerrar).
    meanrev:  z>+entry -> short ETH/long BTC.  z<-entry -> long ETH/short BTC.
    momentum: z>+entry -> long ETH/short BTC.  z<-entry -> short ETH/long BTC."""
    z = zscore(df["ratio"], w).values
    o_btc, o_eth = df["open_btc"].values, df["open_eth"].values
    ts = df["ts"].values
    hi, lo = ("short_eth", "long_eth") if mode == "meanrev" else ("long_eth", "short_eth")
    trades, state, seg = [], "flat", None  # state: long_eth | short_eth | flat

    def close_seg(i_exec):
        st, i0, pxb0, pxe0 = seg
        pxb1, pxe1 = o_btc[i_exec], o_eth[i_exec]
        ret_eth = pxe1 / pxe0 - 1
        ret_btc = pxb1 / pxb0 - 1
        if st == "long_eth":
            gross = NOTIONAL * (ret_eth - ret_btc)
        else:  # short_eth (long btc)
            gross = NOTIONAL * (ret_btc - ret_eth)
        pnl = gross - 4 * NOTIONAL * COST_PER_LEG
        trades.append({"entry_ts": str(ts[i0]), "exit_ts": str(ts[i_exec]), "side": st,
                       "pnl": pnl, "ret_pct": round(100 * gross / NOTIONAL, 3)})

    for i in range(w, len(df) - 1):
        if np.isnan(z[i]):
            continue
        if state == "flat":
            if z[i] > entry_z:
                state, seg = hi, (hi, i + 1, o_btc[i + 1], o_eth[i + 1])
            elif z[i] < -entry_z:
                state, seg = lo, (lo, i + 1, o_btc[i + 1], o_eth[i + 1])
        else:
            crossed = abs(z[i]) < exit_z
            flipped = (state == lo and z[i] > entry_z) or (state == hi and z[i] < -entry_z)
            if crossed or flipped:
                close_seg(i + 1)
                state, seg = "flat", None
                if flipped:  # reentrar al lado opuesto
                    if z[i] > entry_z:
                        state, seg = hi, (hi, i + 1, o_btc[i + 1], o_eth[i + 1])
                    else:
                        state, seg = lo, (lo, i + 1, o_btc[i + 1], o_eth[i + 1])
    if seg is not None:
        close_seg(len(df) - 1)
    return trades


def benchmarks(df: pd.DataFrame) -> dict:
    """Buy&hold de referencia, en $ sobre NOTIONAL=100, neto de 1 round-trip (2 legs)."""
    rt = 2 * COST_PER_LEG
    ret_btc = df["close_btc"].iloc[-1] / df["open_btc"].iloc[0] - 1
    ret_eth = df["close_eth"].iloc[-1] / df["open_eth"].iloc[0] - 1
    return {
        "hold_BTC": round(NOTIONAL * (ret_btc - rt), 2),
        "hold_ETH": round(NOTIONAL * (ret_eth - rt), 2),
        "hold_50_50": round(NOTIONAL * (0.5 * ret_btc + 0.5 * ret_eth - rt), 2),
        "ret_BTC_pct": round(100 * ret_btc, 1),
        "ret_ETH_pct": round(100 * ret_eth, 1),
    }


def by_quarter(trades: list[dict]) -> dict:
    out = {}
    for t in trades:
        q = pd.Timestamp(t["entry_ts"]).to_period("Q").strftime("%Y-Q%q") \
            if hasattr(pd.Timestamp(t["entry_ts"]).to_period("Q"), "strftime") \
            else str(pd.Timestamp(t["entry_ts"]).to_period("Q"))
        out.setdefault(q, []).append(t)
    return {q: {"n": len(ts), "pnl": round(sum(x["pnl"] for x in ts), 2)} for q, ts in sorted(out.items())}


# ───────────────────────── main ─────────────────────────

def main():
    df = load_pair()
    n = len(df)
    mid = n // 2
    df_a, df_b = df.iloc[:mid].reset_index(drop=True), df.iloc[mid:].reset_index(drop=True)
    bench = benchmarks(df)

    print("=" * 100)
    print(f"RATIO-ROTATION BTC<->ETH | {df['ts'].iloc[0]} -> {df['ts'].iloc[-1]} | {n} velas 1h")
    print(f"Costos: {COST_PER_LEG*100:.2f}%/leg (FEE {FEE*100:.1f}% + SLIP {SLIPPAGE*100:.2f}%). NOTIONAL ${NOTIONAL:.0f}/pata")
    print(f"BENCHMARKS buy&hold (neto): BTC ${bench['hold_BTC']} ({bench['ret_BTC_pct']}%) | "
          f"ETH ${bench['hold_ETH']} ({bench['ret_ETH_pct']}%) | 50/50 ${bench['hold_50_50']}")

    # half-life de reversion del ratio
    hl_full = half_life(df["ratio"].values)
    hl_a = half_life(df_a["ratio"].values)
    hl_b = half_life(df_b["ratio"].values)
    print(f"\nHALF-LIFE reversion del ratio (horas): full={hl_full:.0f}  mitadA={hl_a:.0f}  mitadB={hl_b:.0f}")
    print("  (corto+estable entre mitades = mean-reversion explotable; muy distinto o inf = no estacionario)")

    results = {"meta": {"period": [str(df['ts'].iloc[0]), str(df['ts'].iloc[-1])], "candles": n,
                        "cost_per_leg": COST_PER_LEG, "notional": NOTIONAL,
                        "half_life_h": {"full": hl_full, "A": hl_a, "B": hl_b}},
               "benchmarks": bench, "rotation": {}, "spread": {}}

    # grid de sensibilidad
    grid = [(w, ez) for w in (168, 336, 720) for ez in (1.0, 1.5, 2.0)]  # 1/2/4 sem de ventana
    best = None
    trial_sharpes = []  # per-trade sharpe de TODO lo probado (para n_trials honesto del DSR)
    for mode in ("meanrev", "momentum"):
        print("\n" + "-" * 100)
        print(f"MODO 1 — ROTATION long-only [{mode}] (spot HOY, 2 legs/trade, mantiene beta):")
        print(f"{'w/entry_z':<14}{'n':>5}{'WR%':>7}{'PF':>8}{'PnL$':>9}{'DD$':>8}{'Sharpe':>8} | {'PF_A':>6}{'PF_B':>6}")
        for w, ez in grid:
            tr = simulate_rotation(df, w, ez, mode=mode)
            ta = [t for t in tr if t["entry_ts"] < str(df["ts"].iloc[mid])]
            tb = [t for t in tr if t["entry_ts"] >= str(df["ts"].iloc[mid])]
            m, ma, mb = metrics(tr), metrics(ta), metrics(tb)
            key = f"w{w}/z{ez}"
            results["rotation"][f"{mode}/{key}"] = {"full": m, "A": ma, "B": mb}
            if tr:
                trial_sharpes.append(obs_sharpe(np.array([t["pnl"] / NOTIONAL for t in tr])))
            print(f"{key:<14}{m['n']:>5}{m['wr']:>7}{m['pf']:>8}{m['pnl']:>9}{m['max_dd']:>8}{m['sharpe']:>8} | {ma['pf']:>6}{mb['pf']:>6}")

        print(f"\nMODO 2 — SPREAD long/short market-neutral [{mode}] (perps, 4 legs/trade, edge real):")
        print(f"{'w/entry_z':<14}{'n':>5}{'WR%':>7}{'PF':>8}{'PnL$':>9}{'DD$':>8}{'Sharpe':>8} | {'PF_A':>6}{'PF_B':>6}")
        for w, ez in grid:
            tr = simulate_spread(df, w, ez, exit_z=0.5, mode=mode)
            ta = [t for t in tr if t["entry_ts"] < str(df["ts"].iloc[mid])]
            tb = [t for t in tr if t["entry_ts"] >= str(df["ts"].iloc[mid])]
            m, ma, mb = metrics(tr), metrics(ta), metrics(tb)
            key = f"w{w}/z{ez}"
            results["spread"][f"{mode}/{key}"] = {"full": m, "A": ma, "B": mb, "by_quarter": by_quarter(tr)}
            if tr:
                trial_sharpes.append(obs_sharpe(np.array([t["pnl"] / NOTIONAL for t in tr])))
            # "mejor" candidato: PF alto Y robusto en ambas mitades (anti-cherry-pick)
            robust = ma["pf"] != float("inf") and mb["pf"] != float("inf") and ma["pf"] > 1.2 and mb["pf"] > 1.2
            if robust and m["pf"] != float("inf") and (best is None or m["pf"] > best[1]):
                best = (f"{mode}/{key}", m["pf"], tr)
            print(f"{key:<14}{m['n']:>5}{m['wr']:>7}{m['pf']:>8}{m['pnl']:>9}{m['max_dd']:>8}{m['sharpe']:>8} | {ma['pf']:>6}{mb['pf']:>6}")

    # breakdown por trimestre + DEFLATED SHARPE del mejor spread robusto
    if best:
        print(f"\nMejor SPREAD robusto ({best[0]}, PF {best[1]}) — PnL por trimestre (bear 2022 NO incluido):")
        for q, m in by_quarter(best[2]).items():
            print(f"  {q}  n={m['n']:>3}  PnL=${m['pnl']:>8}")
        target_r = np.array([t["pnl"] / NOTIONAL for t in best[2]])
        dsr = deflated_sharpe(target_r, trial_sharpes, n_trials=len(trial_sharpes))
        results["deflated_sharpe_best"] = {"variant": best[0], **dsr}
        print(f"\nDEFLATED SHARPE del mejor ({best[0]}) — correccion por multiple testing:")
        print(f"  n_trials probados={dsr['n_trials']}  sharpe_obs/trade={dsr['sharpe_obs_per_trade']}  "
              f"E[max sharpe por azar]={dsr['expected_max_sharpe_by_chance']}")
        print(f"  PSR_vs_0={dsr['PSR_vs_0']}   *** DSR={dsr['DSR']} ***  (gate: DSR>=0.95)")
        verdict = "PASA el gate DSR — lead real, seguir a walk-forward + bear hold-out" if dsr["DSR"] >= 0.95 \
            else "NO pasa DSR — el PF alto es en gran parte seleccion entre %d trials (mismo error que KidQuant)" % dsr["n_trials"]
        print(f"  VEREDICTO: {verdict}")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    out_f = OUT_DIR / f"ratio_rotation_{stamp}.json"
    out_f.write_text(json.dumps(results, indent=1, default=str))
    print(f"\nGuardado en {out_f}")
    print("\nLECTURA: el gate del jury es el MODO 2 (spread). Si su PF<1.3 o no es robusto A/B,")
    print("no hay edge market-neutral que justifique migrar a perps. La rotation (modo 1) mantiene")
    print("beta: comparar su PnL vs hold_50_50 — si no le gana, el timing del ratio no agrega valor.")


if __name__ == "__main__":
    main()
