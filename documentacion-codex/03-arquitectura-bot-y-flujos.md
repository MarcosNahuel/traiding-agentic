# 03 - Arquitectura del bot y flujos recomendados

## Arquitectura objetivo (alineada al repo)

```text
Market Streams (WS) + User Data Streams
        |
        v
Market State Store (candles, trades, account events)
        |
        v
Indicators Engine (determinista)
        |
        v
Strategy Advisor (LLM -> TradeProposal JSON)
        |
        v
Risk Gate (determinista, hard rules)
        |
        +--> risk_rejected (log + alert)
        |
        +--> validated
              |
              +--> auto_approved (< threshold)
              +--> pending_approval (>= threshold)
                          |
                          +--> approved / rejected / expired
              |
              v
Execution Service (idempotente + filtros + firma)
              |
              v
Order/Event Store
              |
              +--> Reconciliacion por eventos (primaria)
              +--> Reconciliacion por polling (secundaria)
```

## Contratos de dominio recomendados

- `TradeProposal`: salida unica del LLM.
- `ValidatedProposal`: propuesta que paso `RiskGate`.
- `ExecutionIntent`: propuesta lista para ordenar con `clientOrderId`.
- `OrderLifecycleEvent`: `submitted`, `ack`, `partially_filled`, `filled`, `canceled`, `rejected`, `unknown`.

## Arreglos concretos al flujo actual

1. Antes de `placeOrder`, ejecutar `PreTradeChecks`:
- precision/tick size/step size/notional
- limites de cuenta y max open positions
- drift de precio desde aprobacion (`priceDriftGuard`)

2. Separar confirmacion de ejecucion en 3 estados:
- `submitted_to_exchange`
- `execution_unknown`
- `execution_confirmed`

3. Resolver `execution_unknown` con una saga:
- buscar por `clientOrderId`
- esperar evento en user stream
- fallback a query REST
- timeout final -> `manual_review_required`

4. Reconciliacion:
- `event-driven` en tiempo real con user streams
- `polling` cada 60s como red de seguridad

5. Circuit breaker LLM:
- fallback a `NO_TRADE` en vez de repetir ultima decision.

## Reglas de seguridad de ejecucion

1. Kill switch global (`TRADING_ENABLED=false`) por defecto.
2. Claves separadas por entorno y rotacion periodica.
3. Nunca loguear `apiSecret` ni payload firmado completo.
4. Registrar hash de request y response de exchange para auditoria.

## SLOs minimos recomendados

- `proposal_to_execution_p95 < 5s` (auto-aprobadas)
- `reconciliation_divergences = 0` por 48h antes de graduacion
- `order_rejection_rate < 1%` (excluyendo rechazos voluntarios por risk gate)
- `ws_reconnect_success_rate > 99%`

## Gating de rollout

1. Simulador:
- minimo 7 dias, sin breakers criticos.

2. Spot testnet:
- 48h sin divergencias.
- cero ordenes duplicadas por timeout.

3. Spot demo:
- validar limites estilo live.
- validar runbooks de incidentes.

4. Candidato live:
- aprobacion manual de despliegue.
- checklist de seguridad y monitoreo firmado.

