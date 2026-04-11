# Market Regimes — Taxonomía

El bot clasifica el mercado en **5 regímenes** usando `backend/app/services/regime_detector.py`. Cada régimen tiene características distintas y estrategias que funcionan mejor/peor.

## Regímenes

| Régimen | ADX | SMA | Hurst | Estrategia óptima |
|---|---|---|---|---|
| `trending_up` | > 25 | SMA20 > SMA50 | > 0.55 | **01-trend-momentum** ✓ |
| `trending_down` | > 25 | SMA20 < SMA50 | > 0.55 | Ninguna (SHORT no soportado) — evitar |
| `ranging_low_vol` | < 20 | cross | ~0.50 | **01** con filtros exigentes |
| `ranging_high_vol` | < 20 | cross | ~0.50 | **02-reversal-oversold** (idea) |
| `volatile` | variable | cross | variable | Ninguna — reducir size, evitar entradas |

## Cómo se calcula

Ver `backend/app/services/regime_detector.py`:

1. **ADX(14)** para fuerza de tendencia
2. **Comparación SMA20/SMA50** para dirección
3. **Hurst exponent** (~250 samples) para persistencia vs mean-reversion
4. **Confidence score** combinando los tres

## Threshold actual

- `buy_regime_confidence_min = 85.0` → bloquea BUY solo si `trending_down` con convicción alta.
- Esto permite mean-reversion accidental (ver trade del 2026-04-11 que dio +8.40%).

## Cómo debería leer un analista

Cuando el usuario pregunta "reevalúa la estrategia":
1. Verificar régimen actual del símbolo (via regime_detector o market data)
2. Si `trending_up` estable → **01-trend-momentum** sin cambios
3. Si `ranging_high_vol` → considerar activar **02** (aún no implementada)
4. Si `volatile` → recomendar pausar nuevas entradas hasta regime flip

## Links

- Código: `backend/app/services/regime_detector.py`
- Hurst implementation: `backend/app/services/technical_analysis.py`
