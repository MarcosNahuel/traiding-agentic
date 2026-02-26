# Estrategias Breakout y Volatilidad

## Estrategias cubiertas (SSRN 3247865)

- `3.14 Support and resistance`
- `3.15 Channel`
- `3.11/3.12/3.13` MA breakouts
- `7.x` estrategias de volatilidad (adaptables por estructura)
- `6.5` volatility targeting (concepto de control de exposicion)

## Validacion externa (resumen)

- Reglas tecnicas de breakout tienen evidencia historica, pero requieren filtro de ruido.
- En crypto, el riesgo principal es breakout falso durante compresion con baja liquidez.
- Volatility targeting reduce drawdown en muchos contextos cuando se ejecuta con disciplina.

Ver fuentes:

- `fuentes-validadas-2026-02-19.md` (Breakout, MA Rules y Volatility Management)

## Cuando aplicar

### Scalping

- Breakouts cortos en compresion (squeeze) con confirmacion de volumen.
- Requiere execution muy fina para no perder edge.

### Intraday

- Mejor caso de uso: rango previo + expansion de volatilidad + volumen.

### Swing

- Donchian/Channel breakouts con trailing ATR son robustos.

## Spot vs Futures

- Spot: breakout long con riesgo simple.
- Futures: breakout long/short y mejor expresion de volatilidad, pero mayor riesgo de liquidacion.

## Reglas operativas recomendadas

1. Exigir "pre-condicion de compresion" (bandwidth Bollinger bajo).
2. Confirmar breakout con volumen y cierre de vela.
3. Evitar operar durante anuncios macro de alto impacto sin filtro de riesgo.
4. Ajustar tamano por volatilidad (ATR o target-vol).

## Snippet Python (bbands squeeze breakout)

```python
import pandas as pd
import pandas_ta_classic as ta

def squeeze_breakout(df: pd.DataFrame) -> pd.Series:
    close = df["close"]
    bb = ta.bbands(close, length=20, std=2.0)
    upper = bb["BBU_20_2.0"]
    lower = bb["BBL_20_2.0"]
    mid = bb["BBM_20_2.0"]
    bw = (upper - lower) / mid
    vol_ma = ta.sma(df["volume"], length=20)

    squeeze = bw < 0.02
    breakout_up = squeeze.shift(1) & (close > upper) & (df["volume"] > 1.3 * vol_ma)
    exit_long = close < mid

    signal = pd.Series("hold", index=df.index)
    signal[breakout_up] = "buy"
    signal[exit_long] = "sell"
    return signal
```

## Riesgos tipicos

- Overtrading por breakout en cada falsa expansion.
- Slippage alto en velas violentas.
- Falta de hard-stop en reversiones rapidas.

## Recomendacion para este repo

- Prioridad alta: fortalecer `bbands_squeeze` con confirmacion de volumen y ADX.
- Prioridad media: agregar "channel breakout" como estrategia nativa del backtester.
- Prioridad media: incorporar target-vol sizing.
