---
regime: ranging_high_vol
detection: ADX<20 + Hurst<0.45 + ATR%>1.5%
---

# Ranging High Volatility

## Características
- Oscilaciones amplias sin tendencia
- ADX bajo pero ATR alto (>1.5%)
- Wicks frecuentes
- Whipsaws que golpean SL

## Performance histórica del bot
- Este régimen fue parte del problema pre-fix: trades entraban con entropy alta (ruido), ADX bajo, y los SL se activaban por wicks.

## Estrategia activa
**01-trend-momentum con filtros estrictos** o idealmente **02-reversal-oversold** (no implementada).

## Recomendación
- Aumentar `buy_entropy_max` más restrictivo (0.65 en vez de 0.75)
- Aumentar `sl_atr_multiplier` a 1.5 para absorber wicks
- Considerar pausa total del símbolo

## Parámetros óptimos
- `sl_atr_multiplier`: 1.5 (más holgado)
- `tp_atr_multiplier`: 2.5 (potencial mean-reversion)
- Entry requiere volume spike confirmado
- Time stop 12h (mean-reversion debe ser rápida)

## Riesgos
- Whipsaw SL
- Regime flip súbito a trending → perder el move
