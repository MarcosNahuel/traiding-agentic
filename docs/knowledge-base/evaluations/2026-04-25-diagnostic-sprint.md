---
date: 2026-04-25
time: 17:00 UTC
author: Claude Opus 4.7 — diagnostic sprint
trigger: user "el plan está bien pero hoy no funciona" tras Fase 0 + CODEX/15 deep research
---

# Evaluación 2026-04-25 — Diagnostic Sprint

## Contexto

Tras completar Fase 0 (bounds SSOT, approval workflow, derivatives client, partial-exit infra, decomm prep), el bot seguía sin demostrar edge: 79 trades cerrados con P&L flat, alta tasa de SL, posible contaminación por bug del proxy de precios. CODEX/15 §9 explicitó el orden correcto: validar fix del proxy → probar partial-exit con replay → recién después permitir Strategist Agent.

Sprint ejecutado en branch `feat/diagnostic-sprint` (mergeada a master local 2026-04-25, no pusheada).

## Lo que se hizo

1. **Fetch klines reales** desde Binance Live (3 símbolos × 2 intervalos × ~70 días, ~301k filas) para usar como ground truth.
2. **Drift audit** (`02_drift_audit.py`): cruzó 77 trades de Supabase contra klines reales, detectó "ghost SL" (drift > 30 bps + kline real no tocó SL).
3. **Replay engine** (`03_prepare_entries.py` + `04_partial_exit_ab.py`): 4 simuladores de exit (V0-V3) con 15 tests TDD, corridos sobre los 77 entries reales como semilla, contra klines limpias.
4. **Decisión documentada** en `backend/scripts/diagnostics/reports/03-decision-final.md`.

## Hallazgos

### Drift audit — INCONCLUSO

- **8 trades pre-fix con drift > 30 bps**, incluyendo BTC 2026-04-16 con drift -354 bps (exit en 72117 vs Binance close 74763). Patrón clásico de proxy stale.
- **0 trades post-fix con drift > 30 bps**, pero solo n=6 trades en la ventana — insuficiente para confirmar que el fix anduvo.
- 1 ghost SL formal detectado (4.5% del total de SL, todo pre-fix).

**Implicación:** patrón pre-fix sí matchea con el bug del proxy. Pero no podemos confirmar el fix con 6 trades.

### Partial exit A/B — sin edge en ningún variant

| Variante | N | WR | E[R] | PF | Total $ |
|---|---:|---:|---:|---:|---:|
| V0 baseline | 77 | 35.1% | -0.06 | 0.90 | -23.12 |
| **V1 partial+2ATR** | 77 | 36.4% | -0.19 | 0.65 | **-19.53** |
| V2 partial+3ATR | 77 | 24.7% | -0.21 | 0.64 | -22.89 |
| V3 no-partial+3ATR | 77 | 19.5% | -0.43 | 0.59 | -24.99 |

(Notional $100, fees 10 bps round-trip, slippage 5 bps)

- **49% de trades tocaron +1R** antes de cerrar — el dolor operativo que motivó partial-exit es real (consistente con CODEX/15 §2.2).
- V1 mejora marginal $3.59 sobre baseline, **no significativo** con n=77.
- V3 es claramente peor: trail solo no compensa.

## Decisión

| Flag | Decisión | Razón |
|---|---|---|
| `PARTIAL_EXIT_ENABLED` | **NO activar** | Mejora marginal, sin significancia estadística. Complejidad operativa no justifica $3.59 sobre 77 trades. |
| `CHANDELIER_K` | mantener `3.0` | V3 (chandelier solo) es peor que V0. Si más adelante se activa partial, k=2 vence a k=3. |
| `SL_K`, `TP_K` | no tocar | Balance 65/35 SL:TP del baseline actual es razonable. |
| BNB | no promover | Cluster 2026-03-20 con 10 trades casi idénticos sugiere problemas de generación de señal. |

## Próximo paso

**Re-correr este sprint en 2-3 semanas** (~2026-05-15) cuando haya más data post-fix:
1. Drift colapsa a 0% sostenido → proxy fix confirmado.
2. Sample size > 30 trades post-fix → A/B con potencia estadística.
3. Si después de eso hay edge positivo claro (Sharpe OOS > 1.0, PF > 1.2), recién ahí evaluar Fase 1 Strategist Agent.

**El problema real no es el exit, es el edge:** ningún variant es rentable. Cambiar partial-exit no convierte una estrategia perdedora en ganadora.

## Artefactos

- Reportes detallados: `backend/scripts/diagnostics/reports/01-drift-audit.md`, `02-partial-exit-ab.md`, `03-decision-final.md`.
- Pipeline reproducible: `backend/scripts/diagnostics/01_fetch_klines.py` … `04_partial_exit_ab.py`.
- 15 tests TDD: `backend/tests/diagnostics/test_exit_simulators.py`.
- Spec + plan: `docs/superpowers/specs/2026-04-25-diagnostic-sprint-design.md`, `docs/superpowers/plans/2026-04-25-diagnostic-sprint-plan.md`.

## Lecciones

1. **Datos contaminados → conclusiones contaminadas.** Usar klines de Binance Live (públicas) como ground truth fue clave; usar Supabase como semilla y no como fuente de verdad evitó propagar el bug del proxy al replay.
2. **Sample chico + muchas variantes = overfitting risk.** 77 trades, 4 variantes, varios parámetros — la diferencia $3.59 entre V0 y V1 cae claramente dentro del ruido.
3. **CODEX/15 §9 tenía razón:** no saltar a Fase 1 sin validar pasos previos. La infraestructura de Fase 0 es útil, pero activarla sin edge es prematuro.
