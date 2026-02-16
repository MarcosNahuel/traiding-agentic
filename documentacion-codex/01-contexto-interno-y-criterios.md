# 01 - Contexto interno y criterios de implementacion

## Resumen de contexto (interno)

El proyecto define dos fases:

1. Fase 1 (research): agentes que curan fuentes, extraen estrategias y generan una guia maestra.
2. Fase 2 (trading): bot operativo en paper trading (BTCUSDT), con HITL, risk manager y observabilidad.

Este enfoque ya aparece en:

- `docs/plans/2026-02-15-mvp-research-trading-agent-design.md`
- `docs/plans/2026-02-15-fase2-trading-bot-design.md`
- `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md`

## Principios que se mantienen

- El LLM propone, nunca ejecuta directo.
- Risk manager y circuit breakers son deterministas.
- Trazabilidad completa por `correlation_id`.
- Gate por entorno: no permitir ordenes fuera de `spot_testnet`/`demo_futures` (y opcionalmente `spot_demo`).

## Ajustes criticos recomendados sobre el plan actual

1. Idempotencia real:
- No asumir "el exchange ignora duplicados".
- En Binance, un `newClientOrderId` repetido no siempre se ignora: se rechaza si la orden anterior sigue abierta.
- Si hay timeout con estado desconocido, primero consultar estado por `clientOrderId` y solo despues decidir retry.

2. User data stream obligatorio:
- Reconciliacion cada 60s ayuda, pero no reemplaza eventos de cuenta/orden en tiempo real.
- Spot y futures tienen mecanismos distintos (ver doc 02).

3. Validacion previa por filtros de simbolo:
- Antes de enviar orden, validar `PRICE_FILTER`, `LOT_SIZE`, `MIN_NOTIONAL`/`NOTIONAL`, etc., usando `exchangeInfo`.
- Reduce rechazos y activaciones falsas de circuit breakers.

4. Corregir ejemplos TypeScript de interfaces:
- En el plan, algunos campos estan tipeados como literales (`maxDailyLossPct: 2;`) en vez de `number`.
- Si se copia literal, eso restringe el tipo a un unico valor y puede romper extensibilidad.

5. Unificar configuracion de entorno:
- Evitar drift entre `BINANCE_ENV` y `BROKER_ADAPTER`.
- Definir una sola fuente de verdad (por ejemplo `TRADING_ENV`) y derivar adapter/URLs desde ahi.

6. Fallback de LLM:
- Evitar "usar ultima decision" cuando falla LLM.
- Mas seguro: fallback a `NO_TRADE` + alerta.

## Decision operativa recomendada

Para este repo (Next.js + Supabase + AI SDK), mantener arquitectura actual y reforzar:

- Contratos tipados estrictos para `TradeProposal`
- Validacion exchange-side antes de ordenar
- Reconciliacion hibrida: eventos + polling
- Runbooks y SLOs en ops

