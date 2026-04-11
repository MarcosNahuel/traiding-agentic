---
regime: trending_up
detection: ADX>25 + SMA20>SMA50 + Hurst>0.55
---

# Trending Up

## Características
- **Higher highs, higher lows**
- Momentum positivo sostenido
- Rallies con pullbacks moderados (~-2% a -4%)
- Volumen alcista dominante

## Performance histórica del bot
- Los mejores trades post-fix ocurrieron en subidas ETH (mini-trending up)
- Trade +8.40% del 2026-04-11 técnicamente era en trending_down de 66% confidence, pero con oversold snap-back — fue un case edge

## Estrategia activa
**01-trend-momentum** (sin cambios)

## Parámetros óptimos
- `sl_atr_multiplier`: 1.0-1.2
- `tp_atr_multiplier`: 2.0-2.5
- Trailing activation: 30% (actual)

## Riesgos
- Late entry → pullback inmediato → SL
- Trailing demasiado tight cierra winners prematuramente
