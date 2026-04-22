---
regime: ranging_low_vol
detection: ADX<20 + Hurst~0.5 + ATR%<1%
---

# Ranging Low Volatility

## Características
- Precio oscila en canal estrecho
- ADX bajo (<20) — sin tendencia
- ATR% <1% del precio
- Volumen bajo

## Performance histórica del bot
- BTCUSDT post-fix: todos los trades fueron en régimen ranging_low_vol. Resultado: 6 trades con P&L microscópico, ninguno superó 1.6% move.
- Es el "breakeven noise" — el bot abre/cierra sin capturar edge real.

## Estrategia activa
**01-trend-momentum con multipliers tight** (aplicado 2026-04-11 para BTCUSDT):
- `sl_atr_multiplier = 1.0` (vs 1.2 default)
- `tp_atr_multiplier = 1.5` (vs 2.0 default)

## Recomendación
- **Reducir frecuencia o pausar** el símbolo si se mantiene en este régimen >72h
- Aumentar ADX threshold a 22-25 para evitar entrys en rangos muy planos
- Priorizar señales con volume spike >2× (breakout hints)

## Estado en código
- Desde `2026-04-21`, `signal_generator.py` implementa un perfil `range-breakout`
- Ese perfil exige `RSI<=45`, `ADX>=22` y al menos `2` breakout hints
- Si además un símbolo acumula `3` losers consecutivos, se pausa 24h

## Parámetros óptimos
- Filtro ADX más estricto (>22)
- SL/TP tight (1.0 ATR / 1.5 ATR)
- Time stop más corto (12h en vez de 24h)

## Riesgos
- Churn (muchos trades near-breakeven)
- Comisiones erosionan P&L
