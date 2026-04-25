---
title: Implementation Plan — Diagnostic Sprint
date: 2026-04-25
status: in_progress
spec: docs/superpowers/specs/2026-04-25-diagnostic-sprint-design.md
branch: feat/diagnostic-sprint
---

# Implementation Plan — Diagnostic Sprint

## Estructura final

```
backend/scripts/diagnostics/
├── __init__.py
├── 01_fetch_klines.py
├── 02_drift_audit.py
├── 03_replay_engine.py
├── 04_partial_exit_ab.py
├── lib/
│   ├── __init__.py
│   ├── kline_loader.py
│   └── exit_simulators.py
└── reports/
    └── (gitignored except *-final.md)

backend/tests/diagnostics/
├── __init__.py
├── test_exit_simulators.py
└── test_kline_loader.py

data/diagnostics/      # gitignored entirely
├── klines.parquet
├── trades.csv
├── entries_clean.parquet
└── ...
```

## .gitignore additions

```
data/diagnostics/
backend/scripts/diagnostics/reports/*.csv
backend/scripts/diagnostics/reports/01-*
backend/scripts/diagnostics/reports/02-*
!backend/scripts/diagnostics/reports/03-decision-final.md
```

## Orden de implementación (con gates)

### Step 1 — Infra mínima
**Files**: `backend/scripts/diagnostics/__init__.py`, `backend/scripts/diagnostics/lib/__init__.py`, `backend/tests/diagnostics/__init__.py`, `.gitignore` updates.
**Commit**: `chore(diag): scaffold diagnostics directory + gitignore`

### Step 2 — Script 01 fetch_klines
**File**: `backend/scripts/diagnostics/01_fetch_klines.py`

Contrato:
- CLI: `python -m backend.scripts.diagnostics.01_fetch_klines --start 2026-01-01 --end 2026-04-25 --symbols ETHUSDT,BTCUSDT --intervals 1m,1h --out data/diagnostics/klines.parquet`
- Endpoint: `https://api.binance.com/api/v3/klines` (Live, público, sin auth)
- Pagina por chunks de 1000 candles (limit Binance) con backoff y respeta `X-MBX-USED-WEIGHT-1M`
- Schema parquet: `symbol, interval, open_time, open, high, low, close, volume, close_time`
- Idempotente: si parquet existe y cubre el rango, skip; si cubre parcial, completa los faltantes
- Imprime resumen: filas por (symbol, interval), rango de fechas, gaps detectados

**Commit**: `feat(diag): script 01 fetch klines from binance live`

### Step 3 — `lib/kline_loader.py`
Helper para los scripts 02/03/04: lee parquet, slice por símbolo/intervalo/rango, devuelve DataFrame indexado por timestamp UTC. Tests básicos en `tests/diagnostics/test_kline_loader.py` (carga, slicing, manejo de gaps).
**Commit**: `feat(diag): kline_loader helper + tests`

### Step 4 — Export trades.csv
**File**: `data/diagnostics/trades.csv` (gitignored, solo local)
- Vía MCP Supabase `execute_sql` con query: `SELECT id, symbol, side, entry_ts, exit_ts, exit_reason, entry_price, exit_price, sl_price, tp_price FROM positions WHERE status = 'closed' ORDER BY entry_ts ASC`
- Pasarlo a CSV manualmente (1 vez)
- Documentar la query exacta usada en `backend/scripts/diagnostics/SUPABASE_EXPORT.md` (sí committeado, no el CSV)

### Step 5 — Script 02 drift_audit
**File**: `backend/scripts/diagnostics/02_drift_audit.py`

Contrato:
- CLI: `python -m backend.scripts.diagnostics.02_drift_audit --trades data/diagnostics/trades.csv --klines data/diagnostics/klines.parquet --fix-date 2026-04-18 --out backend/scripts/diagnostics/reports/01-drift-audit.md`
- Para cada trade: localizar la kline 1m que contiene `exit_ts`, obtener `binance_close`, calcular `drift_bps = (exit_price - binance_close) / binance_close * 10000`
- Marcar `ghost_sl = (exit_reason == 'STOP_LOSS') AND (abs(drift_bps) > 30) AND (sign(drift_bps) opuesto al SL)`
- Histograma `|drift_bps|` en bins [0,5,10,20,30,50,100,>100], split antes/después de `--fix-date`
- Veredicto:
  - Si % ghost_sl > 20% antes-fix Y < 5% después-fix → "fix funcionó"
  - Si % ghost_sl no cae después-fix → "fix NO funcionó, escalar"
  - Si muestra después-fix < 10 trades → "inconcluso"
- Output: markdown + CSV con todas las filas

**GATE**: Si veredicto = "fix NO funcionó", abortar el sprint y escalar.

**Commit**: `feat(diag): script 02 drift audit + reporte`

### Step 6 — `lib/exit_simulators.py` + tests (TDD)
**Files**: `backend/scripts/diagnostics/lib/exit_simulators.py`, `backend/tests/diagnostics/test_exit_simulators.py`

API:
```python
@dataclass
class ExitResult:
    exit_ts: datetime
    exit_reason: Literal["SL","TP","CHANDELIER","PARTIAL_THEN_CHANDELIER","END_OF_DATA"]
    pnl_r: float            # P&L en R-multiples
    pnl_quote: float        # P&L en quote currency neto fees+slippage
    touched_1r: bool        # ¿alcanzó +1R en algún momento?

def simulate_v0_baseline(entry, klines_1m, atr, sl_k, tp_k, fee_bps, slip_bps) -> ExitResult: ...
def simulate_v1_partial_2atr(entry, klines_1m, atr, sl_k, fee_bps, slip_bps) -> ExitResult: ...
def simulate_v2_partial_3atr(entry, klines_1m, atr, sl_k, fee_bps, slip_bps) -> ExitResult: ...
def simulate_v3_no_partial_3atr(entry, klines_1m, atr, sl_k, tp_k, fee_bps, slip_bps) -> ExitResult: ...
```

Tests obligatorios por simulador (mínimo 4 cada uno):
1. Trade long que toca +1R, luego retrocede y cierra en SL → V0 SL puro; V1/V2 partial al 1R + Chandelier; V3 SL puro
2. Trade long que toca SL antes de cualquier movimiento favorable → todos cierran en SL
3. Trade long con tendencia limpia hasta fin del período → V0 cierra TP; V1/V2 partial + runner sigue; V3 trailing
4. Trade short con condiciones simétricas
5. Edge: ATR = 0 → reject / raise

**Commit**: `feat(diag): exit simulators V0-V3 + tests TDD`

### Step 7 — Script 03 replay_engine
**File**: `backend/scripts/diagnostics/03_replay_engine.py`

Contrato:
- Carga klines 1h (timeframe de la estrategia) y feeds bar-by-bar a `signal_generator.evaluate_signal`
- Respeta `signal_cooldown_minutes` y `max_open_positions` desde config actual
- Output: `data/diagnostics/entries_clean.parquet` con `symbol, entry_ts, side, entry_price, atr_at_entry, sl_atr_multiplier, tp_atr_multiplier`
- Compara con `trades.csv` por (symbol, side, entry_ts ± 1h tolerance) → `match_rate`
- CLI flag `--require-match-rate 0.70` para abortar si baja

**GATE**: Si match_rate < 70%, abortar y escalar.

**Commit**: `feat(diag): script 03 replay engine — re-derivar entries`

### Step 8 — Script 04 partial_exit_ab
**File**: `backend/scripts/diagnostics/04_partial_exit_ab.py`

Contrato:
- Para cada entry en `entries_clean.parquet`, correr V0/V1/V2/V3 sobre klines 1m posteriores hasta exit
- Agregar por variante × símbolo × total
- Métricas:
  - N trades
  - Win rate (% pnl_r > 0)
  - Expectancy/R = mean(pnl_r)
  - Profit factor = sum(pnl_r > 0) / |sum(pnl_r < 0)|
  - Max drawdown (% sobre equity nominal acumulada)
  - % `touched_1r`
  - Total P&L quote neto
- Output: `reports/02-partial-exit-ab.md` (tabla 4×3) + `reports/02-partial-exit-ab.csv`

**Commit**: `feat(diag): script 04 partial exit A/B + reporte`

### Step 9 — `03-decision-final.md`
Síntesis manual (no auto-generada, requiere juicio):
- Leer `01-drift-audit.md` y `02-partial-exit-ab.md`
- Decidir: ¿activar PARTIAL_EXIT_ENABLED? ¿con qué CHANDELIER_K? ¿solo ETH o ambos?
- Caveats: muestra chica, overfitting risk, fees asumidos
- Próximo paso recomendado

Este archivo SÍ committeado.

**Commit**: `docs(diag): decisión final post-replay`

## Constraints

- **No tocar** `backend/app/services/`, `app/`, `vercel.json`, `backend/app/config.py`.
- **No modificar** la DB Supabase (solo SELECT vía MCP).
- **No correr** los scripts contra producción — todo local con datos exportados.
- **No hyperopt** ni búsqueda de parámetros — solo las 4 variantes definidas en spec §4.3.

## Quality gates

- `pytest backend/tests/diagnostics/ -q` debe pasar antes de cada commit que toque `lib/`.
- `python -m backend.scripts.diagnostics.0X_*` debe correr sin warnings ni excepciones.
- Los reportes finales deben ser legibles a ojo desnudo (no JSON crudo, sí markdown con tablas).

## Deferred / out of scope

- Walk-forward (CODEX/15 §6.4) — sprint siguiente si los resultados ameritan.
- Integración derivatives_snapshot como veto — sprint siguiente.
- Pushear branch / PR — al final del sprint, decisión separada.
