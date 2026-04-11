---
date: 2026-04-11
type: analysis
author: Claude Opus 4.6 session
severity: improvement
---

# Análisis de Mejoras — 13 trades post-fix

## TL;DR

Los fixes del 5 abril funcionaron (WR 77%, PF excelente). Este análisis identifica 7 mejoras incrementales, de las cuales **4 fueron implementadas inmediatamente** y 3 quedan para A/B testing futuro.

## Comparativa pre/post fix

| Métrica | Pre-fix (49 trades) | Post-fix (13 trades) | Δ |
|---|---|---|---|
| Win Rate | 36.7% | 76.9% | **+40 pts** |
| P&L | -$18.74 | +$15.94 | **+$34.68** |
| R-mult promedio | -0.28 | +0.62 | +0.90 |
| R winners | +0.65 | +0.84 | +0.19 |
| R losers | -0.83 | -0.13 | **+0.70** |
| Duración loser | 27 h | 4 h | -23 h |
| SL hit % | 82% | 56% | -26 pts |
| TP hit % | 1% | 12% | +11 pts |
| Signal exit % | 15% | 31% | +16 pts |

## 7 Hallazgos

### 1. BTC en breakeven noise
6 trades post-fix, todos < 1.6% de move. BTC se mantiene range-bound.
- **Fix aplicado:** `SYMBOL_SL_ATR_OVERRIDES["BTCUSDT"] = 1.0`, `SYMBOL_TP_ATR_OVERRIDES["BTCUSDT"] = 1.5`

### 2. ETH da 100% del rendimiento
7 trades, 6W/1L, +$15.36 de los +$15.94 totales. El edge está en ETH.
- **Fix aplicado:** `SYMBOL_NOTIONAL_OVERRIDES["ETHUSDT"] = 100.0` (edge-based sizing)

### 3. TP multiplier aún muy ancho (5:1 SL/TP)
9 SL por 2 TP post-fix. Ganadores salen mayormente por signal, no TP.
- **Fix aplicado:** BTC tp_atr bajado a 1.5 (parcial)
- **Pendiente:** Scaled exit 50% @ 1R + resto trailing (idea documentada)

### 4. Trailing 40% aún tarde
Winners ETH promedian +2-3%, el trailing a 40% deja ganancias en la mesa.
- **Fix aplicado:** `progress < 0.30` en trading_loop.py:313

### 5. Breakeven gate 0.30% bloquea BTC winners pequeños
Los trades BTC cerraron con +0.15%, +0.23% (bajo el floor). El breakeven gate bloqueó signal exit, luego reversed.
- **Fix aplicado:** `compute_breakeven_threshold(atr_pct)` adaptativo
  - BTC (ATR 0.5%) → floor 0.30%
  - ETH (ATR 1.5%) → 0.45%
  - High vol → capped 0.80%

### 6. Position size fijo desaprovecha edge
Con WR 77% y R+0.62, Kelly óptimo es ~20%. Estoy en 0.6% ($60/$10k).
- **Fix aplicado:** ETH subido a $100

### 7. Falta OCO nativo en Binance (tech debt)
SL/TP por polling cada 2s. Slippage risk en flash moves.
- **Pendiente** (no implementado). Requiere session dedicada.

## Fixes implementados (2026-04-11)

| # | Fix | Archivos | Status |
|---|---|---|---|
| 1 | Multipliers ATR por símbolo (BTC tighter) | `config.py`, `executor.py` | ✓ |
| 2 | Breakeven gate adaptativo por ATR% | `signal_generator.py` | ✓ |
| 3 | Position size $100 para ETH | `config.py`, `signal_generator.py` | ✓ |
| 4 | Trailing activation 40% → 30% | `trading_loop.py` | ✓ |

## Fixes pendientes (futuras sesiones)

| # | Fix | Esfuerzo | Impacto esperado |
|---|---|---|---|
| 5 | Scaled exit 50/50 (mitad en 1R, mitad trailing) | Medio | Alto |
| 6 | Estrategia reversal-oversold (RSI<20 bypass) | Medio | Medio |
| 7 | OCO orders nativos Binance | Alto | Bajo (slippage reduction) |

## Hipótesis a validar

Con ~30 trades adicionales post-fixes nuevas, deberíamos ver:
- BTC P&L no-negativo (hoy es breakeven noise, tighter caps deberían capturar moves pequeños)
- ETH P&L / trade subir ~66% por el notional aumentado
- Breakeven gate bloqueando menos exits en BTC
- Trailing activando más temprano y protegiendo winners

## Datos fuente

- `positions` table, 62 closed positions totales
- `trade_proposals` table, análisis de reasoning por tag [SL/TP/AUTO/TIME_STOP]
- Queries realizadas: ver código inline en `research/2026-04-11-analysis-queries.md` (no generado aún)

## Links

- Muestra pre-fix: 49 trades entre 2026-02-17 y 2026-04-04
- Muestra post-fix: 13 trades entre 2026-04-05 y 2026-04-11
- Post-mortem que originó los fixes: `./2026-04-05-post-mortem-49trades.md`
