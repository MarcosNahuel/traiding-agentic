---
date: 2026-04-21
type: analysis
author: Codex
status: implemented
---

# Upgrade del algoritmo de decision

## TL;DR

El problema ya no era solo "detectar downtrend". Los resultados de trades mostraban dos fallas mas sutiles:

1. La estrategia activa seguia entrando en mercados laterales porque el codigo no distinguia entre `ranging_low_vol` y `ranging_high_vol`.
2. El sistema analizaba manualmente las rachas malas, pero no usaba esa informacion para frenarse solo.

Por eso el cambio implementado en codigo se enfoco en la **capa de decision**, no en reescribir todo el motor:

- `regime_detector.py` ahora clasifica `ranging_low_vol` y `ranging_high_vol`
- `signal_generator.py` usa perfiles de entrada por regimen
- en laterales exige **breakout hints** reales antes de comprar
- activa un **circuit breaker por simbolo** tras 3 losers consecutivos en menos de 24h
- `quant_risk.py` replica el mismo criterio como segunda barrera

## Lectura de resultados

### 1. Post-mortem 49 trades

El post-mortem de `2026-04-05` mostro que el bot perdio por sobreoperar con filtros destruidos por overrides laxos del LLM: mas churn, entradas tarde y SL/TP absurdos.

Resultado documentado:

- 49 trades cerrados
- P&L: `-$18.74`
- win rate: `36.7%`
- profit factor: `0.50`

Ese problema se corrigio con bounds duros, caps de ATR y anti-churn.

### 2. Mejora post-fix

El analisis de `2026-04-11` mostro que los fixes funcionaron:

- 13 trades
- P&L: `+$15.94`
- win rate: `76.9%`
- losers mucho mas cortos

Pero tambien dejo tres pistas importantes:

- BTC estaba en **breakeven noise**
- ETH concentraba casi todo el edge
- el TP seguia capturandose poco porque muchos winners terminaban saliendo por señal

### 3. Regresion reciente

La evaluacion del `2026-04-21` detecto dos cosas a la vez:

- un bug de ejecucion/precio con el proxy stale
- un problema real del algoritmo en mercados laterales de baja volatilidad

Aunque el bug del proxy explica parte de la degradacion, la investigacion tambien muestra que el bot seguia entrando en rangos donde la estrategia 01 no tiene ventaja clara. La documentacion ya hablaba de `ranging_low_vol`, pero el codigo solo devolvia `ranging`.

## Diagnostico del algoritmo anterior

La estrategia activa era un **trend-momentum multi-filter** con buena base:

- RSI
- ADX
- entropia
- SMA20/SMA50
- Hurst
- cooldown
- breakeven gate

El problema era de **granularidad y enforcement**:

1. El filtro de regimen solo bloqueaba `trending_down` fuerte.
2. `PPO`, `autocorr` y `volume_ratio` estaban mayormente en el reasoning, no en la decision.
3. La knowledge base ya distinguia `ranging_low_vol` y `ranging_high_vol`, pero el runtime no.
4. El bot no tenia un pause automatico por simbolo tras una racha claramente mala.

En otras palabras: el motor tenia filtros buenos, pero le faltaba una capa de "caution real" en lateral.

## Cambios implementados

### 1. Detector de regimen mas fino

Archivo: `backend/app/services/regime_detector.py`

Se agregaron dos estados explicitos:

- `ranging_low_vol`
- `ranging_high_vol`

Esto cierra la brecha entre la taxonomia de `docs/knowledge-base/market-regimes/` y el codigo productivo.

### 2. Perfiles de entrada por regimen

Archivo: `backend/app/services/signal_generator.py`

Se introdujeron perfiles:

- `default`
- `range-caution`
- `range-breakout`
- bloqueos directos para `ranging_high_vol`, `volatile` y `low_liquidity`

Logica nueva:

- en `ranging`, la entrada exige condiciones un poco mas estrictas
- en `ranging_low_vol`, la entrada solo pasa si hay **2 o mas breakout hints**
- en `ranging_high_vol`, no entra la estrategia 01; se pausa hasta tener reversal dedicada

Los breakout hints operativos son:

- `PPO > 0`
- `autocorr_1 > 0.02`
- `volume_ratio >= 1.05`

Con esto, `PPO` y `autocorr` dejan de ser decorativos y pasan a pesar en la decision.

### 3. Circuit breaker por simbolo

Archivo: `backend/app/services/signal_generator.py`

Si un simbolo acumula `3` trades perdedores consecutivos y el ultimo cierre fue hace menos de `24h`, el bot bloquea nuevas compras en ese simbolo temporalmente.

Esto automatiza una regla que ya estaba en la KB como red flag de reevaluacion.

### 4. Segunda barrera en risk middleware

Archivo: `backend/app/services/quant_risk.py`

La validacion cuantitativa ahora tambien bloquea entradas en:

- `ranging_high_vol`
- `low_liquidity`

Asi el criterio no depende solo del signal generator.

## Fundamento tecnico

### Por que endurecer el lateral

La evidencia interna del repo es clara: cuando el mercado entra en rango estrecho, la estrategia de trend-following produce churn, round-trips pequenos y erosion por costos.

Eso ademas encaja con la literatura:

- Hurst, Ooi y Pedersen muestran que el trend-following tiene edge robusto, pero no porque funcione igual en cualquier micro-regimen; su fortaleza esta en el shape de retornos y en los movimientos persistentes.
- Dudia, Kumar y Bhattacharyya usan el Hurst exponent precisamente para separar comportamiento de tendencia, mean reversion y random walk.
- El paper `AdaptiveTrend` en crypto enfatiza dos puntos que coinciden con esta mejora: descomposicion por regimen y trailing/gestion adaptados al regimen.

La conclusion practica para este repo es directa:

- en `trending_up`, dejar que el motor 01 trabaje
- en `ranging_low_vol`, pedir evidencia extra de breakout
- en `ranging_high_vol`, no fingir que una estrategia de trend-following puro resuelve un problema de reversal

### Por que el circuit breaker es correcto

El repo ya hacia reevaluaciones manuales cuando un simbolo degradaba. Automatizar una pausa corta despues de 3 losers consecutivos reduce dos riesgos:

- seguir operando un simbolo sin edge actual
- contaminar la muestra con mas trades malos antes de revisar

Es una medida conservadora: no reescribe la estrategia, solo evita insistir ciegamente.

## Que NO cambie en esta sesion

No implemente estas mejoras todavia:

- scaled exit 50/50
- OCO nativo en Binance
- estrategia 02 reversal-oversold
- alineacion completa de `strategy_replay.py` con la nueva taxonomia

La razon es simple: el pedido era mejorar el **algoritmo de decision actual** con cambios defendibles y de bajo riesgo. Esos otros puntos son valiosos, pero pertenecen mas a ejecucion/salida o a una estrategia nueva.

## Verificacion ejecutada

Tests corridos localmente:

- `pytest backend/tests/test_signal_generator.py backend/tests/test_regime_detector.py backend/tests/test_quant_risk.py -q`
- `pytest backend/tests/test_qs_strategies.py backend/tests/test_position_sizer.py backend/tests/test_backtester_strategies.py -q`

Resultado: `55 passed`

## Impacto esperado

Esperaria tres efectos concretos:

1. Menos entradas en lateral sin expansion real.
2. Menos churn en simbolos que vienen degradando.
3. Menor gap entre lo que dicen `decision-matrix.md` y `strategies/01-trend-momentum.md` y lo que realmente ejecuta el bot.

No espero que este cambio arregle por si solo los problemas de ejecucion del proxy stale. Eso sigue siendo otra linea de trabajo.

## Fuentes internas

- `docs/knowledge-base/research/2026-04-05-post-mortem-49trades.md`
- `docs/knowledge-base/research/2026-04-11-improvements-analysis.md`
- `docs/knowledge-base/evaluations/2026-04-21-2107.md`
- `docs/knowledge-base/decision-matrix.md`
- `docs/knowledge-base/market-regimes/ranging-low-vol.md`

## Fuentes externas

- Brian Hurst, Yao Hua Ooi, Lasse Heje Pedersen, *A Century of Evidence on Trend-Following Investing*  
  https://ssrn.com/abstract=2993026

- Ashwin Dudia, Vivek Kumar, Ritabrata Bhattacharyya, *Short Term Trading Model for Asian Equity Index Futures – Using Hurst Exponent*  
  https://ssrn.com/abstract=3543079

- Duc Bui, Thanh Nguyen, *Systematic Trend-Following with Adaptive Portfolio Construction: Enhancing Risk-Adjusted Alpha in Cryptocurrency Markets*  
  https://arxiv.org/abs/2602.11708

- Jiadong Liu, Fotis Papailias, *Time series reversal in trend-following strategies*  
  https://ssrn.com/abstract=2971875
