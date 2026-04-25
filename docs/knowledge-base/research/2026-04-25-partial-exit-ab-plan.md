---
date: 2026-04-25
type: experiment-plan
status: ready
related_spec: docs/superpowers/specs/2026-04-24-daily-strategist-agent-design.md
---

# Partial Exit 50% @ 1R — A/B Test Plan

## Hypothesis

Partial exit 50% del position size cuando current_price >= entry + 1R, con
SL del runner movido a breakeven, captura ganancia mientras el trailing
chandelier se encarga del resto.

Síntoma a atacar: 78% STOP_LOSS / 3% TAKE_PROFIT histórico (200 últimas
proposals). Si la hipótesis funciona, ratio mejora.

## Pre-requisito

Phase 0.1 cumplida: drift del proxy < 1% en >90% de los últimos 10-20 trades
post-redeploy de `f6ba148`.

## Plan

### Baseline (Variant A) — `PARTIAL_EXIT_ENABLED=false`
- Acumular 30 trades cerrados con flag OFF.
- Métricas a guardar (script ad-hoc o consulta SQL):
  - P&L medio por trade
  - Win rate
  - Profit factor
  - SL hit %, TP hit %, signal exit %
  - Drawdown máximo

### Variant B — `PARTIAL_EXIT_ENABLED=true`
- Setear flag en `.env` del backend (Dokploy) y redeploy.
- Acumular 30 trades cerrados.
- Mismas métricas.

### Decisión

Mantener `PARTIAL_EXIT_ENABLED=true` si y solo si:
- P&L medio mejora >=10% vs baseline.
- Drawdown no aumenta >20%.
- Variant B no introduce nuevos bugs (errores en logs).

Si no se cumple, revertir a OFF y documentar resultado.

## Chandelier 3ATR experiment (post-A/B)

Después del A/B partial exit, considerar segundo experimento:
`CHANDELIER_K=3.0` (clásico 22-period × 3ATR) vs `2.0` actual.

Mismo formato: 30 trades pre vs 30 trades post.

## Notes

- No correr ambos experimentos en paralelo.
- No tocar otros parámetros durante un experimento.
- Documentar resultado en `evaluations/YYYY-MM-DD-partial-exit-ab.md`.
