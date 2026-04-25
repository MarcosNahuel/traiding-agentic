---
title: Diagnostic Sprint — Decisión Final
date: 2026-04-25
sprint: docs/superpowers/specs/2026-04-25-diagnostic-sprint-design.md
inputs:
  - 01-drift-audit.md
  - 02-partial-exit-ab.md
---

# Decisión Diagnostic Sprint — 2026-04-25

## Contexto en 3 líneas

Antes de activar `PARTIAL_EXIT_ENABLED` en producción, corrimos drift audit (¿el fix del proxy eliminó SL fantasma?) y A/B replay de 4 variantes de exit sobre los 77 trades históricos contra klines reales de Binance Live. La pregunta operativa: ¿partial-exit cambia el outcome en datos limpios?

## Drift audit

**Veredicto: INCONCLUSO** (post-fix muy chico — 1 SL real desde 2026-04-18).

**Evidencia:**
- Pre-fix: 8 trades con `|drift| > 30 bps`, **incluyendo BTC 2026-04-16 con drift -354 bps** (exit en 72117 vs close real 74763 — patrón clásico de proxy stale).
- Post-fix: 0 trades con drift > 30 bps, pero solo n=6 trades en la ventana.
- 1 ghost SL detectado (4.5% del total de SL), todo en período pre-fix.

**Implicación:** el patrón pre-fix sí matchea con el bug del proxy y el fix parece haber funcionado, pero **la muestra post-fix es insuficiente para confirmarlo**. Necesitamos otras 2-3 semanas de operación post-fix antes de afirmar que el proxy está sano.

## Partial exit A/B

**Variante "menos mala": V1 (partial 50%@1R + Chandelier k=2)**
**Pero ningún variant tiene edge positivo.**

| Variante | N | WinRate | E[R] | Profit Factor | Total $ |
|---|---:|---:|---:|---:|---:|
| V0 baseline (fixed SL/TP) | 77 | 35.1% | -0.06 | 0.90 | **-23.12** |
| **V1 partial+2ATR** | 77 | 36.4% | -0.19 | 0.65 | **-19.53** |
| V2 partial+3ATR | 77 | 24.7% | -0.21 | 0.64 | -22.89 |
| V3 no-partial+3ATR | 77 | 19.5% | -0.43 | 0.59 | -24.99 |

(Notional $100 por trade, fees 10 bps round-trip, slippage 5 bps.)

**Hallazgos clave:**

1. **49% de trades tocaron +1R antes de cerrar** — el dolor operativo que motiva partial-exit es real (consistente con CODEX/15 §2.2).
2. **V1 mejora $3.59 sobre baseline** — diferencia marginal, no estadísticamente significativa con n=77.
3. **V0 baseline tiene 50 SL y 27 TP** — relación 65/35, mejor de lo que sugería el conteo histórico (CODEX/15 §1: 78% SL / 3% TP). El SL_K=1.2 actual ya está balanceando.
4. **V3 (no partial, trail 3ATR) es claramente peor** — pierde más, max DD más profundo. Confirma que trail solo, sin partial, no compensa.
5. **POST-FIX (n=6) es ruido estadístico** — BTC ganó, ETH perdió. No se puede inferir.

**Caveats serios:**
- Muestra chica (77 trades, ~21 BNB casi duplicados del cluster 2026-03-20).
- Replay usa entries reales como semilla → contaminados por proxy stale en el pre-fix. El A/B mide "qué hubiera pasado con esos entries", no "qué hubiera pasado si la estrategia hubiera entrado limpiamente".
- Sin walk-forward, sin OOS, sin Deflated Sharpe — mucho overfitting risk.
- Fees 0.10% spot, sin partial fills, sin min notional explícito.

## Recomendación

| Flag | Decisión | Razón |
|---|---|---|
| `PARTIAL_EXIT_ENABLED` | **NO activar todavía** | Mejora marginal sin evidencia estadística. La complejidad operativa del partial-exit no justifica $3.59 sobre 77 trades. |
| `CHANDELIER_K` | Mantener config actual | V3 (chandelier solo) es peor que V0. Si en el futuro se activa partial, k=2 vence a k=3 en este dataset. |
| `SL_K`, `TP_K` | No tocar | El balance 65/35 SL:TP del baseline actual es razonable, no hay evidencia de mejora con cambios. |
| Símbolos | No promover BNB | El cluster 2026-03-20 (10 trades casi idénticos) sugiere que BNB tuvo problemas de generación de señal. ETH y BTC son los datasets útiles. |

**El problema real no es el exit, es el edge:** ningún variant es rentable. Cambiar partial-exit no convierte una estrategia perdedora en ganadora. CODEX/15 §1 ya lo decía: "edge no probado". Confirmado con datos limpios.

## Próximo paso

**Lo que hace falta antes de cualquier activación productiva nueva:**

1. **Esperar 2-3 semanas más** de trades post-fix limpios para validar:
   - Drift colapsa a 0% sostenido.
   - Sample size > 30 trades post-fix para A/B con potencia estadística.
2. **Re-correr este sprint** sobre el dataset extendido (`/loop` cada semana es razonable).
3. **NO activar el Strategist Agent (Fase 1)** hasta que el bot demuestre edge positivo (Sharpe OOS > 1.0, PF > 1.2 sostenido).

**Lo que NO hace falta hacer ahora:**
- Tocar parámetros (SL_K, TP_K, CHANDELIER_K).
- Activar partial-exit.
- Promover BNB.
- Migrar a Freqtrade/Jesse/Nautilus.

## Out of scope (sprints futuros)

- Walk-forward report (CODEX/15 §6.4).
- Integrar `derivatives_snapshot` como veto en `signal_generator`.
- ATR-based sizing dinámico.
- Filtro time-of-day por iliquidez.

## Artefactos

- `backend/scripts/diagnostics/reports/01-drift-audit.md` — drift audit completo.
- `backend/scripts/diagnostics/reports/02-partial-exit-ab.md` — A/B detallado.
- `backend/scripts/diagnostics/reports/02-partial-exit-ab-V*.csv` — un CSV por variante para análisis ad-hoc.
- `data/diagnostics/klines.parquet` — 301k filas, ground truth Binance Live (gitignored).
- `data/diagnostics/entries.parquet` — 77 entries con ATR computado (gitignored).
