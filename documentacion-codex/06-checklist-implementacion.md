# 06 - Checklist de implementacion y operacion

## A) Checklist tecnico previo

1. Configuracion
- [ ] `TRADING_ENABLED=false` por defecto.
- [ ] Unica variable de entorno para routing (`TRADING_ENV`).
- [ ] Claves por entorno (no reutilizar entre testnet/demo/live).

2. Data y ejecucion
- [ ] Market stream WS estable.
- [ ] User data stream activo y parseado.
- [ ] Reconexion automatica con resuscripcion.
- [ ] Keepalive implementado donde aplique.

3. Ordenes
- [ ] `clientOrderId` generado por propuesta.
- [ ] Validacion de filtros (`exchangeInfo`) antes de enviar.
- [ ] Manejo de `timeout_unknown` con consulta por `clientOrderId`.
- [ ] No retry ciego.

4. Riesgo
- [ ] Risk gate determinista antes de toda orden.
- [ ] Circuit breakers activos (trading/infra/llm).
- [ ] Fallback LLM a `NO_TRADE`.
- [ ] Kill switch probado.

5. Auditoria
- [ ] `correlation_id` en todo el flujo.
- [ ] Logs inmutables (sin delete operativo).
- [ ] Historial de decisiones humanas en HITL.

## B) Checklist de simulador (7 dias)

- [ ] Sin divergencias de reconciliacion por 48h continuas.
- [ ] Error rate de ejecucion < 1%.
- [ ] Breakers criticos = 0.
- [ ] PnL no dependiente de un solo trade outlier.
- [ ] Runbooks de incidentes probados.

## C) Checklist de paso a Spot Testnet / Spot Demo

- [ ] Firma y reloj validados contra server time.
- [ ] Rate limiter funcionando (sin 429 sostenidos).
- [ ] Todos los rechazos de orden son explicables.
- [ ] Flujo HITL (approve/reject/expire) validado E2E.
- [ ] Reconciliacion hibrida (eventos + polling) en verde.

## D) Runbooks minimos

1. WS caido
- pausar nuevas ordenes
- reconectar y resuscribir
- comparar snapshot vs cache local

2. `execution_unknown`
- consultar por `clientOrderId`
- esperar user event
- escalar a revision manual si persiste

3. Rechazos masivos
- auditar filtros y precision
- revisar rate limits y timestamp drift
- bloquear trading hasta causa raiz

4. Breaker de perdida diaria
- bloquear ordenes nuevas
- cerrar posiciones segun politica
- notificar operador y registrar post-mortem

## E) KPIs operativos diarios

- `fill_rate`
- `order_rejection_rate`
- `slippage_bps_realized`
- `reconciliation_divergences`
- `proposal_to_execution_ms_p95`
- `breaker_trigger_count`
- `llm_cost_usd_daily`

