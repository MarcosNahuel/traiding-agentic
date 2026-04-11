---
id: NN-name
name: Strategy Display Name
status: active | idea | deprecated
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
category: trend-following | mean-reversion | breakout | arbitrage | ml
---

# Nombre de la estrategia

## Resumen (1-2 líneas)

Qué hace y cuándo se usa.

## Cuándo funciona mejor

- Régimen: trending_up / trending_down / ranging / volatile
- Volatilidad: low / medium / high (ATR% range)
- Timeframe: 1h / 4h / 1d
- Símbolos testeados: BTCUSDT, ETHUSDT...

## Cuándo NO usarla

- Regímenes que la rompen
- Market conditions a evitar

## Reglas de entrada (BUY)

| Filtro | Valor | Por qué |
|---|---|---|
| RSI(14) | < X | ... |
| ADX(14) | > X | ... |
| ... | | |

## Reglas de salida (SELL)

| Tipo | Trigger | Prioridad |
|---|---|---|
| Hard SL | -X*ATR | 1 (fast loop 2s) |
| Hard TP | +X*ATR | 1 (fast loop 2s) |
| Trailing | Chandelier | 2 (fast loop 2s) |
| Signal exit | RSI + MACD | 3 (slow loop 60s) |
| Time stop | 24h | 4 |

## Parámetros (con paths file:line)

```
sl_atr_multiplier = 1.2          # backend/app/config.py:59
tp_atr_multiplier = 2.0          # backend/app/config.py:60
breakeven_gate = 0.30% floor     # backend/app/services/signal_generator.py:50
```

## Performance histórica

- Muestra: N trades entre YYYY-MM-DD y YYYY-MM-DD
- Win rate: X%
- Profit factor: X
- R-mult promedio: X
- P&L: $X
- Drawdown máx: -$X

## Links

- Código: `backend/app/services/signal_generator.py`
- Investigación de soporte: `../research/YYYY-MM-DD-*.md`
- Paper/fuente externa: URL
