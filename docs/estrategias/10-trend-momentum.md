# Estrategias Trend y Momentum

## Estrategias cubiertas (SSRN 3247865)

- `3.1 Price-momentum`
- `3.2 Earnings-momentum` (adaptable como momentum de eventos)
- `3.7 Residual momentum`
- `3.11/3.12/3.13` cruces de medias moviles
- `10.4 Trend following (momentum)` en futuros
- `19.2 Fundamental macro momentum` como filtro de contexto

## Validacion externa (resumen)

- Momentum es una anomalia robusta en multiples mercados.
- En crypto hay evidencia de momentum y tambien de reversions segun horizonte.
- En cripto 24/7 el control de costos y filtros de regimen pesa mas que en equity.

Ver fuentes:

- `fuentes-validadas-2026-02-19.md` (secciones Momentum y Crypto Momentum)

## Cuando aplicar

### Scalping (1m-5m)

- Solo con confirmacion de volumen y volatilidad util.
- Evitar en ruido puro (ADX bajo + entropy alta).

### Intraday (5m-1h)

- Mejor ventana para cruces de medias + filtro de tendencia.
- Ideal en BTCUSDT y ETHUSDT por liquidez.

### Swing (4h-1d)

- Funciona bien en rupturas de regimen persistente.
- Usar stops por ATR y trailing para evitar devolver profit.

## Spot vs Futures

- Spot: version long-only (mas simple, menor riesgo operacional).
- Futures: long/short simetrico, pero obliga control estricto de apalancamiento y funding.

## Reglas operativas recomendadas

1. No abrir si `regime=volatile` con alta confianza.
2. Requerir confirmacion de pendiente en SMA50/SMA200.
3. Filtrar por volumen relativo (`vol_actual > 1.2 * vol_media`).
4. Stop basado en ATR y no solo en porcentaje fijo.

## Snippet Python (momentum con filtro de regimen)

```python
import pandas as pd
import pandas_ta_classic as ta

def trend_momentum_signal(df: pd.DataFrame) -> pd.Series:
    close = df["close"]
    vol = df["volume"]

    sma_fast = ta.sma(close, length=20)
    sma_slow = ta.sma(close, length=50)
    adx = ta.adx(df["high"], df["low"], close, length=14)["ADX_14"]
    vol_ma = ta.sma(vol, length=20)

    long_entry = (
        (sma_fast > sma_slow) &
        (sma_fast.shift(1) <= sma_slow.shift(1)) &
        (adx > 25) &
        (vol > 1.2 * vol_ma)
    )

    long_exit = (
        (sma_fast < sma_slow) |
        (adx < 18)
    )

    signal = pd.Series("hold", index=df.index)
    signal[long_entry] = "buy"
    signal[long_exit] = "sell"
    return signal
```

## Riesgos tipicos

- Falsos quiebres en lateralidad.
- Sobreoptimizacion de ventanas de MA.
- Costos ocultos en alta frecuencia (fees + slippage).

## Recomendacion para este repo

- Prioridad alta: extender `sma_cross` con filtros de ADX/volumen/regimen.
- Prioridad alta: crear version `trend_following_futures` solo para Demo Futures.
- Prioridad media: residual momentum multi-asset.
