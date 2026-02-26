# Priorizacion de Estrategias para Este Repo

Objetivo: elegir las estrategias mas convenientes para BTC/Binance (Spot + Futures), en scalping/intraday/swing, usando el estado real del codigo actual.

## Criterios de ranking

1. Robustez empirica y simplicidad operacional.
2. Compatibilidad con infraestructura actual del repo.
3. Sensibilidad a costos (fees, slippage, funding).
4. Riesgo de ruina y complejidad de monitoreo.
5. Tiempo de implementacion.

## Matriz de conveniencia (1-5)

| Familia | Spot | Futures | Scalping | Intraday | Swing | Complejidad | Conveniencia total |
|---|---:|---:|---:|---:|---:|---:|---:|
| Trend/Momentum con filtros | 5 | 5 | 3 | 5 | 5 | 2 | 5 |
| Mean Reversion con regime gate | 4 | 4 | 4 | 5 | 3 | 2 | 5 |
| Breakout + volatilidad | 4 | 5 | 4 | 5 | 4 | 3 | 4 |
| Carry/Basis en perp futures | 2 | 5 | 2 | 4 | 5 | 4 | 4 |
| Pairs/StatArb | 3 | 4 | 3 | 4 | 4 | 4 | 3 |
| Market Making | 2 | 4 | 5 | 4 | 1 | 5 | 2 |
| ML/Sentiment puro | 3 | 3 | 3 | 4 | 4 | 5 | 2 |

## Que ya esta implementado

- `sma_cross`, `rsi_reversal`, `bbands_squeeze`:
  - `backend/app/services/backtester.py`
- Indicadores y features:
  - `backend/app/services/technical_analysis.py`
- Deteccion de regimen:
  - `backend/app/services/regime_detector.py`
- Riesgo cuantitativo (8 checks):
  - `backend/app/services/quant_risk.py`

Gap principal:

- Estrategia en vivo todavia placeholder:
  - `backend/app/services/strategy.py`

## Roadmap recomendado

## Fase 1 (alta prioridad, implementacion inmediata)

1. `trend_momentum_v2` con ADX + volumen + ATR stops.
2. `mean_reversion_v2` con gate de rango y timeout.
3. `bbands_breakout_v2` con confirmacion de volumen.

Entrega:

- Senales deterministicas reproducibles + backtests con costos realistas.

## Fase 2 (prioridad media)

1. `futures_basis_monitor` (funding + basis edge neto).
2. `pairs_cointegration` en universos limitados (BTC/ETH/BNB).
3. Volatility targeting para position sizing.

## Fase 3 (prioridad selectiva)

1. `market_making_sandbox` en demo.
2. `ml_meta_filter` sobre estrategias deterministicas.
3. Sentiment solo con pipeline anti-spam y anti-poisoning.

## Reglas de despliegue

1. Ninguna estrategia pasa a live sin backtest + forward test + limites de riesgo.
2. No usar leverage alto en fases iniciales.
3. Mantener kill-switch y degradacion segura ante errores de exchange.

## Decision final recomendada

Para este repositorio, el mejor stack inicial es:

1. Trend/Momentum filtrado.
2. Mean Reversion filtrado.
3. Breakout de volatilidad filtrado.
4. Luego carry/basis en Futures Demo.

Esta combinacion maximiza relacion valor/tiempo de implementacion y minimiza riesgo operacional temprano.
