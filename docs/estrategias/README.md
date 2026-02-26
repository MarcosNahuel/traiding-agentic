# Base de Conocimiento de Estrategias (BTC/Binance)

Este folder organiza las estrategias para que el agente de codificacion pueda decidir rapido que implementar, cuando usar cada enfoque y con que riesgos operativos.

## Estructura

1. `01-taxonomia-ssrn-151.md`
2. `10-trend-momentum.md`
3. `20-mean-reversion.md`
4. `30-breakout-volatilidad.md`
5. `40-arbitraje-y-statarb.md`
6. `50-market-making-y-microestructura.md`
7. `60-ml-y-sentiment.md`
8. `70-derivados-carry-y-basis.md`
9. `80-riesgo-ejecucion-binance.md`
10. `90-contexto-argentina.md`
11. `99-priorizacion-implementacion.md`
12. `fuentes-validadas-2026-02-19.md`

## Como usar esta base

1. Empezar por `99-priorizacion-implementacion.md` para elegir roadmap.
2. Validar restricciones operativas en `80-riesgo-ejecucion-binance.md`.
3. Elegir familia de estrategia (trend, mean reversion, breakout, etc.).
4. Aplicar snippets de cada archivo en backtests reproducibles.
5. Revalidar contra contexto local en `90-contexto-argentina.md`.

## Estado actual del repo (resumen)

- Ya hay backtester para `sma_cross`, `rsi_reversal`, `bbands_squeeze`.
- Ya hay `regime_detector` y middleware de riesgo cuantitativo.
- Falta engine de estrategia en vivo (archivo placeholder).
- Integracion actual de ejecucion: Binance Spot via proxy.

Referencias de codigo:

- `backend/app/services/backtester.py`
- `backend/app/services/regime_detector.py`
- `backend/app/services/quant_risk.py`
- `backend/app/services/strategy.py`
- `backend/app/services/binance_client.py`
