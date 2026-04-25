---
title: Diagnostic Sprint — Drift Audit + Partial Exit Replay
date: 2026-04-25
status: approved
owner: nahuel
related:
  - docs/superpowers/specs/2026-04-24-daily-strategist-agent-design.md
  - CODEX/15-deep-research-repos-patrones-aplicados-2026-04-25.md
  - docs/knowledge-base/research/2026-04-25-partial-exit-ab-plan.md
  - backend/scripts/check_proxy_drift.py
  - backend/app/services/trading_loop.py
research_inputs:
  - "Deep Research #2 (CODEX/15, 2026-04-25): §1 (62 trades flat P&L, 78% SL / 3% TP, bug proxy invalida histórico), §6 (top 5 mejoras priorizadas), §9 (orden de validación)"
---

# Diagnostic Sprint — Drift Audit + Partial Exit Replay

## 1. Goal

Antes de activar `PARTIAL_EXIT_ENABLED`, tocar parámetros de la estrategia, o avanzar a Fase 1 del Strategist Agent, **responder con datos limpios** dos preguntas que hoy están abiertas:

1. **¿El fix del proxy de precios eliminó los SL fantasma?**
   Cuántos de los 62 SL históricos fueron disparados por proxy stale y no por movimiento real del mercado, y si el drift colapsó después de la fecha del fix.

2. **¿Partial exit 50%@1R + Chandelier 2ATR/3ATR mejora expectancy sobre baseline en datos limpios?**
   Sobre un set de trades re-derivado contra klines reales (no contaminado por proxy), comparar 4 variantes y obtener un veredicto data-driven.

El output del sprint es un **`03-decision.md`** que dice "activar / no activar" cada flag con evidencia, no un compromiso de cambio.

## 2. Why now

Cita CODEX/15 §9: *"el orden correcto es: (1) validar que el fix del proxy eliminó falsos stops, (2) centralizar bounds, (3) approval workflow, (4) probar partial exit con replay/backtest, (5) Futures data read-only, (6) recién después permitir que Claude Strategist proponga cambios diarios."*

Fase 0 cubrió (2) (3) y dejó la infraestructura de (4) (5), pero **nunca corrimos (1) ni (4)**. Activar `PARTIAL_EXIT_ENABLED` sin replay sería otra hipótesis ciega; los 7 días "alentadores" post-fix pueden ser ruido sin el drift audit.

CODEX/15 §1 también es explícito: *"el bug del proxy invalida parte de la lectura histórica de stops"*. Trabajar sobre los 62 trades de Supabase como ground truth contamina cualquier conclusión.

## 3. Non-goals

- **No** modifica `signal_generator.py`, `trading_loop.py`, ni ningún path productivo.
- **No** agrega indicadores nuevos.
- **No** optimiza parámetros (no hyperopt — CODEX/15 §6.1 desaconseja explícito por riesgo de overfitting con muestra chica).
- **No** activa flags. Solo recomienda.
- **No** entra Fase 1 del Strategist Agent.

## 4. Architecture

Todos los scripts viven en `backend/scripts/diagnostics/`. Son standalone, idempotentes, sin efectos sobre la DB productiva.

```
backend/scripts/diagnostics/
├── 01_fetch_klines.py        # baja klines reales Binance Live → parquet local
├── 02_drift_audit.py         # cruza Supabase trades vs klines → reporte drift
├── 03_replay_engine.py       # motor event-driven mínimo sobre klines
├── 04_partial_exit_ab.py     # corre 4 variantes y arma comparativa
├── lib/
│   ├── kline_loader.py       # helper: lee parquet, slice por símbolo/período
│   └── exit_simulators.py    # implementa baseline / partial+2ATR / partial+3ATR / no-partial+3ATR
└── reports/                  # gitignored, salvo *-final.md
    ├── 01-drift-audit.md
    ├── 01-drift-audit.csv
    ├── 02-partial-exit-ab.md
    ├── 02-partial-exit-ab.csv
    └── 03-decision-final.md
```

### 4.1 Flujo de datos

```
Binance REST (Live, no testnet)
        │
        ↓
[01_fetch_klines.py]
        │
        ↓
data/diagnostics/klines.parquet     ←────── ground truth
        │
        ├──→ [02_drift_audit.py] ←── trades.csv (export Supabase)
        │            │
        │            ↓
        │     reports/01-drift-audit.md
        │
        └──→ [03_replay_engine.py]
                     │
                     ↓
              entries_clean.parquet
                     │
                     ↓
              [04_partial_exit_ab.py]
                     │
                     ↓
              reports/02-partial-exit-ab.md
                     │
                     ↓
              reports/03-decision-final.md
```

### 4.2 Componentes

| Script | Responsabilidad única | Input | Output |
|---|---|---|---|
| `01_fetch_klines.py` | Bajar klines 1m + 1h ETHUSDT/BTCUSDT del período de los 62 trades, guardar parquet | API Binance Live (público), rango fechas CLI | `data/diagnostics/klines.parquet` |
| `02_drift_audit.py` | Para cada trade, comparar precio de SL/TP en DB vs close real Binance al mismo timestamp. Marcar "ghost SL" si `\|drift_bps\| > 30` (≈ 3× spread típico testnet). Histograma antes/después fix | `trades.csv` (export desde Supabase via MCP `execute_sql`, schema esperado: `id, symbol, side, entry_ts, exit_ts, exit_reason, entry_price, exit_price, sl_price, tp_price`), `klines.parquet` | `reports/01-drift-audit.md` + CSV |
| `03_replay_engine.py` | Re-derivar entries ejecutando lógica actual (`signal_generator.evaluate_signal`) contra klines reales. Output limpio independiente de Supabase | `klines.parquet`, código actual de señales | `entries_clean.parquet` + reporte de match-rate vs DB |
| `04_partial_exit_ab.py` | Sobre `entries_clean`, simular 4 variantes de exits y comparar | `entries_clean.parquet`, `klines.parquet` | `reports/02-partial-exit-ab.md` + CSV |

### 4.3 Variantes A/B (script 04)

Idénticas a CODEX/15 §2.3:

SL_K y TP_K se leen desde `backend/app/config.py` (valores actuales en producción al momento del replay) para que la comparativa refleje la estrategia real, no una hipotética.

| ID | SL inicial | TP / partial | Trailing |
|---|---|---|---|
| **V0 baseline** | ATR×`sl_atr_multiplier` | TP fijo ATR×`tp_atr_multiplier` | sin trailing |
| **V1 partial+2ATR** | ATR×`sl_atr_multiplier` | partial 50% @ 1R | Chandelier `k=2` sobre runner |
| **V2 partial+3ATR** | ATR×`sl_atr_multiplier` | partial 50% @ 1R | Chandelier `k=3` sobre runner |
| **V3 no-partial+3ATR** | ATR×`sl_atr_multiplier` | TP fijo ATR×`tp_atr_multiplier` | Chandelier `k=3` sobre toda la posición |

Métricas reportadas por variante × símbolo (ETH, BTC, total):

- N trades
- Win rate
- Expectancy en R-multiples
- Profit factor
- Max drawdown (% sobre capital nominal)
- % trades que tocaron +1R antes de SL
- Total P&L neto de fees (fees: 0.10% spot maker/taker, conservador)

## 5. Reportes

### 5.1 `01-drift-audit.md` (después del paso 2)

Estructura:
- Resumen ejecutivo (3 líneas): N ghost SL / N total, % drift > umbral, fecha fix proxy.
- Tabla por trade: `trade_id | side | entry_ts | exit_ts | exit_reason | proxy_price | binance_close | drift_bps | ghost_flag | post_fix?`
- Histograma drift bps antes vs después del fix.
- **Veredicto**: "fix funcionó / no funcionó / inconcluso".

**Decisión que habilita**: si fix funcionó → los 7 días post-fix son representativos. Si no → escalo y paro el sprint, hay un bug abierto.

### 5.2 `02-partial-exit-ab.md` (después del paso 4)

Estructura:
- Match rate entries reproducidos vs Supabase. Si < 70% escalo antes de leer el resto.
- Tabla 4×3 (variantes × ETH/BTC/total) con todas las métricas.
- Equity curve por variante (CSV adjunto, no gráfico inline).
- Análisis cualitativo: ¿qué variante minimiza max DD? ¿cuál maximiza expectancy/R? ¿hay diferencia ETH vs BTC?

### 5.3 `03-decision-final.md` (1 página, en git, no gitignored)

Estructura fija:

```
# Decisión Diagnostic Sprint — 2026-04-XX

## Contexto en 3 líneas
...

## Drift audit
Veredicto: ...
Evidencia: ...

## Partial exit A/B
Variante ganadora: V?
Evidencia: ...
Caveats (overfitting risk, muestra chica, etc.): ...

## Recomendación
- PARTIAL_EXIT_ENABLED: SI/NO
- CHANDELIER_K: X
- Aplicar a: ETHUSDT solo / ambos
- Próximo paso: ...
```

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Match rate de entries reproducidos < 70% (cambió la lógica de señales desde los 62 trades) | Reportar match rate explícito. Si baja, abortar replay y escalar — datos no son comparables. |
| Klines Binance Live vs Spot Testnet difieren | Usar Live para ground truth (klines públicas). Documentar en el reporte. |
| Muestra chica (62 trades históricos → quizás <50 reproducidos) | CODEX/15 §1 ya lo dice: hipótesis viva, edge no probado. Reporte debe ser explícito sobre baja confianza estadística. No hyperopt. |
| Fees / slippage subestimados | Usar 0.10% spot fee + 5 bps slippage como conservador. Documentar en el reporte. |
| Bug en `exit_simulators.py` que invalida toda la comparativa | Tests unitarios obligatorios para cada simulador antes de correr el A/B. Casos: trade que toca +1R y vuelve a SL, trade que toca SL antes que TP, trade que cierra al final del período. |

## 7. Definition of Done

- [ ] `01-drift-audit.md` committeado con veredicto.
- [ ] `02-partial-exit-ab.md` committeado con tabla y match rate.
- [ ] `03-decision-final.md` committeado con recomendación clara SI/NO por flag.
- [ ] Tests unitarios de `exit_simulators.py` pasando (mínimo 4 casos por simulador).
- [ ] `data/diagnostics/` y `reports/0[12]-*` agregados a `.gitignore`.
- [ ] No hay cambios en código productivo (`backend/app/services/`, `app/`, `vercel.json`).
- [ ] Branch `feat/diagnostic-sprint` con todos los commits, listo para merge.

## 8. Out of scope (siguiente sprint según resultados)

- Activar `PARTIAL_EXIT_ENABLED=true` en Dokploy (post-decisión, requiere monitoreo separado).
- Walk-forward report (CODEX/15 §6.4) — depende de tener replay engine maduro.
- Integrar `derivatives_snapshot` como veto en `signal_generator` (CODEX/15 §6.3).
- ATR-based sizing (CODEX/15 §6.5).
- Fase 1 Strategist Agent.
