---
id: 02-reversal-oversold
name: Mean-Reversal Oversold Snap
status: idea
created: 2026-04-11
last_updated: 2026-04-11
category: mean-reversion
---

# Mean-Reversal Oversold Snap (propuesta, no implementada)

## Resumen

Entra **long** cuando un activo está en oversold extremo (`RSI < 20` o Z-score < -2) incluso contra la tendencia dominante, apostando al snap-back mean-reversion. Sale rápido en reversión a la media.

## Motivación (de datos reales)

El trade que generó **+8.40% ($9.20)** el 2026-04-11 04:01 UTC en ETHUSDT fue una entrada con:
- RSI = 16.7 (muy oversold)
- Régimen = `trending_down` con 66.8% confianza
- PPO = -0.63% (bearish)
- SMA20 > SMA50 (alineación alcista marginal)

La única razón por la que la estrategia 01 lo permitió fue que la confianza del downtrend (66.8%) estaba **por debajo del umbral de bloqueo** (85%). Fue suerte. Sin ese margen, la mejor señal del mes habría sido suprimida.

Esta estrategia formaliza ese patrón en lugar de dejarlo al azar.

## Cuándo funciona mejor

- Después de moves fuertes (dump >3% en <4h)
- En símbolos de alta liquidez (ETH, BTC)
- Cuando el régimen downtrend NO tiene convicción (conf 50-75%)

## Cuándo NO usarla

- Régimen `trending_down` con conf > 85% (downtrend con convicción → no snap)
- Flash crashes durante eventos macro (news, hacks)
- Altcoins ilíquidas

## Reglas de entrada (BUY) propuestas

| Filtro | Valor |
|---|---|
| RSI(14) | **< 20** (vs < 50 de la estrategia 01) |
| ATR% | < 5% (evitar crashes extremos) |
| Downtrend regime conf | **< 80%** (downtrend débil aceptable) |
| Bollinger Band | Precio < BB lower |
| Volume confirmation | Volume > 2× SMA20 (capitulation) |
| Post-close cooldown | > 60 min (más corto que strategy 01) |

## Reglas de salida propuestas

| Tipo | Trigger |
|---|---|
| Hard SL | -1.5 × ATR (más tight porque hit rápido si falla) |
| **Target 1** | RSI > 40 (cerrar 50%) |
| **Target 2** | RSI > 55 (cerrar resto) |
| Time stop | **6 horas** (si no snap-back, wrong call) |

## Implementación estimada

- Nuevo módulo: `backend/app/services/signal_generator_reversal.py`
- O branch en `signal_generator.py:_evaluate_symbol` con flag
- Registro separado en `positions.strategy_id`
- Tests en `backend/tests/test_reversal_strategy.py`
- A/B test: habilitar solo para ETHUSDT 30 trades, comparar con 01

## Performance esperada (hipótesis)

- Win rate: 55-70% (mean reversion suele ser high WR, low R)
- R-mult promedio: +0.3 a +0.5
- Frecuencia: 1-3 trades/semana (eventos raros)

## Riesgos

- **Catching falling knives:** si el downtrend acelera, SL se golpea rápido
- **Selection bias:** un solo trade exitoso no valida la estrategia
- **Overlap con strategy 01:** si ambas habilitan a la vez, pueden abrir posiciones duplicadas

## Status

**IDEA** — no implementada. Requiere:
1. Backtesting con data histórica (>100 eventos RSI<20)
2. Decisión de A/B test vs canary
3. Aprobación del usuario antes de production
