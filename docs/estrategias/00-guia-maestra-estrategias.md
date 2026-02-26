# Guia Maestra de Estrategias (BTC/Binance)

Esta guia sintetiza el paper `ssrn-3247865.pdf`, la documentacion del repo y la validacion web de estrategias para definir que conviene implementar primero en Python para trading algoritmico.

## 1) Universo completo

- Inventario total: `01-taxonomia-ssrn-151.md`
- Cobertura: 174 entradas (incluyendo sub-variantes del indice del paper).
- Estrategias mas relevantes para este caso de uso:
  - Trend/Momentum
  - Mean Reversion
  - Breakout/Volatilidad
  - Carry/Basis en derivados
  - Pairs/StatArb (segunda etapa)
  - Market Making (etapa avanzada)
  - ML/Sentiment (meta-filtro, no motor primario al inicio)

## 2) Seleccion por horizonte

## Scalping

- Priorizar: breakout + micro mean reversion con filtros de ruido.
- Evitar al inicio: market making real sin infra robusta.

## Intraday

- Priorizar: momentum filtrado + mean reversion en rango + breakout validado por volumen.
- Agregar luego: basis intradia en futures demo.

## Swing

- Priorizar: trend following + carry/basis + filtros macro/regimen.
- Evitar sobreapalancamiento.

## 3) Seleccion por mercado

## Binance Spot

- Foco inicial recomendado:
  1. `sma_cross` mejorado
  2. `rsi_reversal` filtrado por rango
  3. `bbands_squeeze` con confirmacion de volumen

## Binance Futures (Demo)

- Foco segunda etapa:
  1. Trend long/short con reglas simetricas
  2. Funding/basis monitor
  3. Calendar spread simulator

## 4) Regla de priorizacion final

Implementar en este orden:

1. Trend/Momentum v2
2. Mean Reversion v2
3. Breakout/Volatilidad v2
4. Carry/Basis Futures Demo
5. Pairs/StatArb
6. Market Making
7. ML/Sentiment avanzado

Justificacion: maximiza relacion robustez/tiempo de implementacion y minimiza riesgo operacional en fases tempranas.

## 5) Contexto argentino obligatorio

Aplicar siempre:

1. Filtro de friccion local (`spread_usdt_mep`, `spread_usdt_oficial`).
2. Trazabilidad de PnL en USDT y ARS.
3. Seguimiento regulatorio (CNV PSAV + comunicaciones BCRA relevantes).
4. Politica conservadora de riesgo en periodos de stress cambiario local.

Detalle: `90-contexto-argentina.md`

## 6) Checklist tecnico para el agente de codificacion

1. Leer `80-riesgo-ejecucion-binance.md`.
2. Normalizar ordenes con filtros `PRICE_FILTER`, `LOT_SIZE`, `MIN_NOTIONAL`.
3. Usar `newClientOrderId` para idempotencia.
4. Integrar regime + entropy + size checks antes de cualquier orden.
5. Backtest con costos realistas antes de activar ejecucion.

## 7) Mapa de archivos

1. `README.md`
2. `01-taxonomia-ssrn-151.md`
3. `10-trend-momentum.md`
4. `20-mean-reversion.md`
5. `30-breakout-volatilidad.md`
6. `40-arbitraje-y-statarb.md`
7. `50-market-making-y-microestructura.md`
8. `60-ml-y-sentiment.md`
9. `70-derivados-carry-y-basis.md`
10. `80-riesgo-ejecucion-binance.md`
11. `90-contexto-argentina.md`
12. `99-priorizacion-implementacion.md`
13. `fuentes-validadas-2026-02-19.md`
