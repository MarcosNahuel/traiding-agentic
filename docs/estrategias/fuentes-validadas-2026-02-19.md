# Fuentes Validadas (2026-02-19)

Este archivo lista las fuentes usadas para validar estrategias, ejecucion en Binance y contexto argentino.

## A) Fuente base del inventario de estrategias

1. SSRN - 151 Trading Strategies (Kakushadze, Serur)
   - https://ssrn.com/abstract=3247865

## B) Evidencia de estrategias (papers/articulos tecnicos)

## Momentum / Trend / MA Rules

1. Brock, Lakonishok, LeBaron (technical trading rules)
   - https://www.journals.uchicago.edu/doi/10.1086/261713
2. Moving average timing (paper reportado en SSRN)
   - https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461
3. Momentum and reversal in cryptocurrency markets
   - https://www.journals.uchicago.edu/doi/10.1086/720483

## Mean Reversion / Pairs / StatArb

1. Gatev, Goetzmann, Rouwenhorst - Pairs Trading
   - https://academic.oup.com/rfs/article/19/3/797/1646694
2. Distance-based pairs trading evidence
   - https://www.sciencedirect.com/science/article/abs/pii/S0378426608005841
3. Mean-reversion and momentum in crypto (estudio empirico)
   - https://www.sciencedirect.com/science/article/pii/S0378426621000934

## Arbitraje / Funding / Perpetual Futures

1. Bitcoin cross-exchange arbitrage (teoria y empirica)
   - https://arxiv.org/abs/2406.05049
2. Funding-rate carry en perp futures
   - https://arxiv.org/abs/2510.00164
3. Funding rate and perpetual futures dynamics
   - https://www.sciencedirect.com/science/article/pii/S1057521924000576

## Market Making / Microestructura

1. High Frequency Trading in a Limit Order Book (Avellaneda-Stoikov)
   - https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1416153

## C) Binance oficial (operacion y restricciones)

## Spot Testnet y Spot API

1. Spot Testnet WebSocket API - General info
   - https://developers.binance.com/docs/binance-spot-api-docs/testnet/websocket-api/general-api-information
2. Spot Testnet WebSocket Streams
   - https://developers.binance.com/docs/binance-spot-api-docs/testnet/web-socket-streams
3. Spot Trading Endpoints
   - https://developers.binance.com/docs/binance-spot-api-docs/rest-api/trading-endpoints
4. Spot Filters (`PRICE_FILTER`, `LOT_SIZE`, `MIN_NOTIONAL`)
   - https://developers.binance.com/docs/binance-spot-api-docs/filters

## Futures USDT-M

1. General info (incluye demo base URLs)
   - https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info
2. Funding Rate History endpoint
   - https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History

## D) Contexto Argentina (regulatorio y macro operativo)

## Regulatorio

1. CNV - Registro PSAV
   - https://www.cnv.gov.ar/SitioWeb/ProveedoresServiciosActivosVirtuales/RegistrosPSAV
2. BCRA Comunicacion A 7506 (PDF)
   - https://www.bcra.gob.ar/Pdfs/comytexord/A7506.pdf
3. BCRA Comunicacion A 7759 (PDF)
   - https://www.bcra.gob.ar/Pdfs/comytexord/A7759.pdf

## Datos de tipo de cambio y referencia local

1. BCRA - Principales variables
   - https://www.bcra.gob.ar/PublicacionesEstadisticas/Principales_variables.asp
2. BCRA API estadisticas
   - https://api.bcra.gob.ar/estadisticas/v3.0/Monetarias
3. Cotizacion dolar MEP (referencia de mercado)
   - https://www.ambito.com/contenidos/dolar-mep.html

## Notas de calidad de evidencia

1. Se priorizaron documentos oficiales de exchange y reguladores para ejecucion y compliance.
2. Para rendimiento de estrategias se usaron papers y fuentes tecnicas primarias.
3. Donde la fuente publica no fue accesible por scraping (bloqueos 403/404), se uso URL primaria igualmente para trazabilidad.
