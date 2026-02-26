# Estrategias Mean Reversion

## Estrategias cubiertas (SSRN 3247865)

- `3.8 Pairs trading`
- `3.9 Mean-reversion single cluster`
- `3.9.1 Mean-reversion multiple clusters`
- `3.10 Mean-reversion weighted regression`
- `4.4 ETF Mean-reversion` (adaptable por concepto)
- `10.3 Contrarian trading (mean-reversion)` en futuros

## Validacion externa (resumen)

- Mean reversion es sensible al horizonte: puede rendir intradia y fallar en tendencias largas.
- En crypto existe evidencia mixta: periodos de fuerte tendencia destruyen estrategias contrarian.
- Pairs trading mejora cuando se exige cointegracion y control de ruptura estructural.

Ver fuentes:

- `fuentes-validadas-2026-02-19.md` (Mean Reversion y Pairs Trading)

## Cuando aplicar

### Scalping (1m-5m)

- Solo en mercados en rango (ADX bajo, Hurst cercano o menor a 0.5).
- Mejor con pares muy liquidos.

### Intraday (5m-1h)

- Excelente para rebotes a media (BBands/RSI/z-score) con limites de tiempo.

### Swing (4h-1d)

- Menor probabilidad de exito si hay cambios macro o noticias de alto impacto.

## Spot vs Futures

- Spot: bueno para buy-the-dip controlado sin leverage.
- Futures: permite contrarian short, pero el riesgo de squeeze es alto.

## Reglas operativas recomendadas

1. Activar solo si `regime=ranging`.
2. Bloquear si ADX sube rapido (inicio de tendencia).
3. Definir timeout por operacion para evitar quedar atrapado.
4. Usar take-profit parcial sobre media y stop duro por ATR.

## Snippet Python (z-score mean reversion)

```python
import pandas as pd
import pandas_ta_classic as ta

def mean_reversion_signal(df: pd.DataFrame, window: int = 50) -> pd.Series:
    close = df["close"]
    ma = ta.sma(close, length=window)
    std = close.rolling(window).std()
    z = (close - ma) / std
    rsi = ta.rsi(close, length=14)
    adx = ta.adx(df["high"], df["low"], close, length=14)["ADX_14"]

    buy = (z < -2.0) & (rsi < 30) & (adx < 20)
    sell = (z > 0.0) | (rsi > 55)

    signal = pd.Series("hold", index=df.index)
    signal[buy] = "buy"
    signal[sell] = "sell"
    return signal
```

## Riesgos tipicos

- "Knife catching" durante caidas tendenciales.
- Correlaciones inestables en pairs trading crypto.
- Comisiones consumen edge cuando target es chico.

## Recomendacion para este repo

- Prioridad alta: mejorar `rsi_reversal` con filtro de rango (`ADX < umbral`).
- Prioridad media: agregar pairs trading cointegration en backtester.
- Prioridad media: sumar salida por timeout y salida parcial.
