---
regime: trending_down
detection: ADX>25 + SMA20<SMA50 + Hurst>0.55
---

# Trending Down

## Características
- **Lower lows, lower highs**
- Momentum negativo sostenido
- Bounces débiles
- Fear/capitulation en volumen

## Performance histórica del bot
- Cualquier BUY en downtrend >85% confidence está **explícitamente bloqueado** (`signal_generator.py:334`)
- Pre-fix: múltiples trades BNB perdieron en downtrends por entry frames muy laxos (clamp LLM roto)

## Estrategia activa
**NINGUNA** — bloquear nuevas entradas.

El bot NO soporta SHORT (solo spot long). En downtrend fuerte, **la mejor acción es no operar**.

## Excepciones
- **Strategy 02 (reversal-oversold)** — puede entrar en downtrend débil (conf 50-80%) apostando a snap-back. No implementada aún.

## Parámetros óptimos
- Si forzoso entrar: `sl_atr_multiplier` 0.8 (muy tight), time stop 6h
- Position size reducido al 50% del default

## Riesgos
- Catching falling knives
- Drawdown acumulativo si el regime persiste
