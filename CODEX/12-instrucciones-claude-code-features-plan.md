# Instrucciones para Claude Code - Agregar Features al Plan Maestro

Usa este prompt tal cual en Claude Code:

```text
Objetivo:
Actualizar el documento `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md` para incorporar features faltantes detectadas en el reporte `docs/02-2026/deep-research-report (2).md`, manteniendo las correcciones ya aplicadas (Gemini 2.5, seguridad SSRF, Binance env router, jobs async, etc.).

Reglas de trabajo:
1. Edita SOLO el archivo del plan.
2. No borres secciones existentes; mejora y extiende.
3. Mantén coherencia técnica entre arquitectura, SQL, API routes, frontend, seguridad, testing y roadmap.
4. Si una recomendación del reporte contradice el plan actual o documentación oficial, deja nota de decisión técnica en una subsección “Decisión de diseño”.
5. Usa español técnico, directo y accionable.

Cambios obligatorios (feature set mínimo):

A) HITL real (Human-in-the-Loop)
- Agregar sección nueva: “HITL Workflow”.
- Definir máquina de estados para `TradeProposal`:
  - `draft -> pending_approval -> approved|rejected -> executed|expired|cancelled`
- Agregar SLA de aprobación y expiración (ej. 5 min).
- Agregar regla: sin aprobación humana explícita NO se ejecuta orden.
- Incluir flujo de interrupción/manual approval (patrón interrupt).

B) Reconciliación + idempotencia de ejecución
- Agregar sección “Execution Reliability”.
- Definir idempotencia con `client_order_id` único por propuesta.
- Definir reconciliación periódica:
  - consultar órdenes abiertas/estado/posiciones
  - reparar divergencias entre DB y exchange
- Agregar política de retry/backoff y dead-letter para órdenes fallidas.

C) Circuit Breakers de riesgo
- Extender Risk Manager con breakers globales:
  - `max_daily_loss_pct`
  - `max_consecutive_losses`
  - `max_order_rejections_per_hour`
  - `max_slippage_bps`
  - `latency_guard_ms`
- Definir acción al disparar breaker:
  - bloquear nuevas órdenes
  - cerrar/hedgear según regla determinista
  - generar alerta operativa

D) Event sourcing auditable (inmutable)
- Extender `agent_logs` o agregar tabla dedicada de eventos inmutables.
- Requisitos:
  - hash del evento (`event_hash`)
  - hash previo (`prev_hash`) para cadena auditable
  - `correlation_id` end-to-end (proposal -> order -> fill)
  - timestamps y actor (`agent|human|system`)
- Incluir ejemplo de payload de evento.

E) Simulador/Broker paper determinista
- Agregar sección “Simulated Broker Adapter”.
- Definir que la primera ejecución es contra simulador local (no exchange directo).
- Modelar fill simplificado con slippage configurable.
- Condición para pasar a Binance demo:
  - X días estables
  - errores por debajo de umbral
  - breakers sin activaciones críticas

F) Endpoints y UI para aprobación humana
- Agregar API routes nuevas:
  - `POST /api/proposals` (crear propuesta)
  - `GET /api/proposals?status=pending_approval`
  - `POST /api/proposals/[id]/approve`
  - `POST /api/proposals/[id]/reject`
  - `POST /api/reconciliation/run`
  - `GET /api/risk/breakers`
- Agregar páginas frontend:
  - `/approvals` (cola HITL)
  - `/operations` (estado breakers, reconciliación, eventos)

G) Modelo de datos (SQL) a agregar
- Agregar tablas (o equivalente):
  1. `trade_proposals`
  2. `execution_orders`
  3. `reconciliation_runs`
  4. `risk_breaker_events`
  5. `event_store` (si no reutilizas `agent_logs`)
- Constraints requeridos:
  - `client_order_id` UNIQUE
  - integridad referencial proposal->orders
  - índices por `status`, `created_at`, `correlation_id`

H) Observabilidad operativa mínima
- Nueva subsección “Operational Metrics (MVP)” con KPIs:
  - proposal_to_approval_ms
  - approval_to_execution_ms
  - fill_rate
  - rejection_rate
  - slippage_bps_realized
  - breaker_trigger_count
  - llm_tokens/cost por agente

I) Testing ampliado (obligatorio)
- Añadir tests de:
  - transición de estados HITL
  - idempotencia (doble submit)
  - reconciliación ante estado divergente
  - disparo de circuit breaker
  - e2e “propuesta -> aprobación -> ejecución simulada”

J) Roadmap actualizado
- Semana 1: incluir HITL + propuestas + simulador base.
- Semana 2: reconciliación + idempotencia + breakers.
- Semana 3: observabilidad + operaciones dashboard.
- Semana 4: endurecimiento + piloto Binance demo (si pasa criterios).

K) Sección final “Definition of Done”
- Añadir checklist de salida:
  - no hay ejecución sin aprobación humana
  - reconciliación automática activa
  - idempotencia validada por tests
  - breakers operativos
  - trazabilidad completa por correlation_id

Entregable esperado:
1. Documento actualizado completo.
2. Resumen al final con:
  - qué se agregó
  - qué se modificó
  - decisiones de diseño tomadas
  - riesgos pendientes (si los hay)
```

## Nota operativa

Si Claude detecta mojibake en `deep-research-report (2).md`, debe ignorar problemas de encoding y usar solo el contenido semántico de las recomendaciones.

