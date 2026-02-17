# 13 - CODEX ultima version (ruta validada para desarrollo)

Fecha de cierre: 2026-02-15 (US)
Plan base auditado: `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md`
Documentos cruzados: `docs/plans/*.md`, `docs/02-2026/deep-research-report*.md`, `CODEX/01..12`

## Estado ejecutivo

- Fase 1 (Research Agent): `GO`
- Fase 2 (Trading Bot paper): `GO condicionado`
- Condicion para Fase 2: cerrar primero los controles de ejecucion Binance, idempotencia y reconciliacion de esta guia.

## Decisiones cerradas (baseline tecnico)

1. Stack base aprobado:
   - Next.js 16 + React 19
   - Node.js `>=20.9.0`
   - Supabase PostgreSQL + pgvector
   - Vercel AI SDK + provider Google
2. Modelos aprobados:
   - LLM: `gemini-2.5-flash`
   - Embeddings: `gemini-embedding-001`
3. Vector store aprobado:
   - `VECTOR(1024)` para `paper_chunks.embedding`
   - Indice HNSW
4. Seguridad base obligatoria desde MVP:
   - RLS activo en todas las tablas
   - Fetcher con hardening SSRF
5. Ejecucion de trading aprobada por fases:
   - Primero `BROKER_ADAPTER=simulated`
   - Luego Spot Testnet / Futures Demo solo si pasa gates de simulacion

## Cambios obligatorios para dejar camino limpio al agente implementador

### P0 (hacer antes de escribir logica de trading)

1. Congelar versiones en codigo (no "latest"):
   - Definir versiones exactas en `package.json`.
   - Confirmar con `pnpm install --frozen-lockfile` y `pnpm tsc --noEmit`.
2. Cerrar API de embeddings en una sola firma:
   - Mantener sintaxis consistente en todo el repo.
   - Usar `providerOptions.google.outputDimensionality=1024`.
   - Validar por typecheck y test de smoke.
3. Implementar fetcher seguro (SSRF):
   - Validacion URL, bloqueo de redes privadas/metadata, timeout, max bytes, content-type whitelist.
4. Definir cola async para tareas largas:
   - Reader/extraction/embedding no deben depender del request-response directo.
5. RLS + politicas:
   - Habilitar RLS y crear politicas explicitas para `service_role` y accesos de app.

### P0 de Fase 2 (antes de enviar una orden al exchange)

1. Idempotencia real:
   - `client_order_id` unico por propuesta.
   - `UNIQUE(client_order_id)` en `execution_orders`.
2. Binance runtime guardrails:
   - Rechazar orden si `BINANCE_ENV` no es `spot_testnet` o `demo_futures`.
   - `TRADING_ENABLED=false` por defecto.
3. Validacion de reglas de simbolo:
   - Obtener y aplicar filtros de `exchangeInfo` antes de crear orden.
4. User stream + reconciliacion hibrida:
   - Consumir eventos de cuenta/orden por WebSocket API.
   - Complementar con polling de reconciliacion periodica (ej: 60s).
5. Gestion de sesion WebSocket:
   - Manejar ping/pong y reconexion controlada.
6. Time sync y ventana de recepcion:
   - Sincronizar reloj con servidor Binance y usar `recvWindow`.

## Plan de implementacion validado (paso a paso + gate)

### Paso 1 - Foundation de runtime y dependencias

- Accion:
  - Crear proyecto base y fijar engines Node.
  - Bloquear versiones de librerias core.
- Gate:
  - `pnpm install --frozen-lockfile`
  - `pnpm lint && pnpm tsc --noEmit`
- Salida:
  - Build reproducible en local y CI.

### Paso 2 - Base de datos y seguridad de datos

- Accion:
  - Migraciones SQL para tablas Fase 1 + RLS.
  - `paper_chunks.embedding VECTOR(1024)` + HNSW.
- Gate:
  - Script de smoke SQL: insert/select/rpc.
  - Test de autorizacion (rol anon no debe leer tablas internas).
- Salida:
  - Persistencia lista para pipeline research.

### Paso 3 - Source Agent con fetch seguro

- Accion:
  - Evaluacion de fuentes con schema estricto.
  - Fetcher SSRF-safe.
- Gate:
  - Tests unitarios de validacion URL y bloqueo de destinos privados.
  - Test de integracion de evaluacion con fuente mock.
- Salida:
  - Fuentes pasan de `pending` a `approved/rejected` de forma trazable.

### Paso 4 - Reader Agent + embeddings + map-reduce

- Accion:
  - Chunking, embedding y extraccion estructurada.
  - Evitar truncamiento bruto en papers largos (map-reduce).
- Gate:
  - Test de regression para documentos >30k chars.
  - Verificacion de dimension embedding (1024) en DB y RPC.
- Salida:
  - Extracciones consistentes sin perdida silenciosa de contexto.

### Paso 5 - Synthesis Agent versionado

- Accion:
  - Generar guia maestra con control de contexto (batching/top-N).
  - Versionado atomico y unico.
- Gate:
  - Test de concurrencia (dos generaciones simultaneas).
  - Verificar `version` unica y orden temporal.
- Salida:
  - Guia maestra estable para consumo de chat y trading.

### Paso 6 - Chat RAG calibrado

- Accion:
  - Embedding de pregunta + RPC `match_chunks`.
  - Ajuste de `match_threshold` con dataset de evaluacion.
- Gate:
  - Benchmark offline (precision@k / recall@k).
  - Pruebas de calidad con preguntas control.
- Salida:
  - Respuesta del chat con contexto relevante y trazable.

### Paso 7 - Workflow HITL y aprobaciones

- Accion:
  - Implementar maquina de estados de `trade_proposals`.
  - SLA de aprobacion, expiracion y rechazo.
- Gate:
  - Tests de transicion de estados (todos los caminos).
  - E2E de `/approvals` con approve/reject/timeout.
- Salida:
  - No hay ejecucion sin pasar por workflow de propuesta.

### Paso 8 - Broker adapter + Binance hardening

- Accion:
  - Simulated broker primero.
  - Adaptadores Spot Testnet / Futures Demo luego.
  - Validacion de filtros, idempotencia, user streams y keepalive.
- Gate:
  - Integracion proposal -> approval -> execution con `client_order_id`.
  - Prueba de reconexion WS y reconciliacion por divergencia.
- Salida:
  - Ejecucion paper robusta y auditable.

### Paso 9 - Riesgo, breakers y observabilidad

- Accion:
  - Breakers trading/infra/LLM.
  - Metricas operativas y costos LLM por agente.
- Gate:
  - Tests de activacion/desactivacion de breakers.
  - Alertas funcionando (aprobaciones, errores, presupuesto).
- Salida:
  - Operacion bajo control con trazabilidad de punta a punta.

### Paso 10 - Go/No-Go de simulacion a exchange demo

- Accion:
  - Evaluar estabilidad en simulador y luego en demo exchange.
- Gate:
  - Minimo 7 dias estables, error rate bajo, reconciliacion sin divergencias criticas.
- Salida:
  - Decision objetiva de graduacion, sin salto prematuro.

## Definition of Done operativo para el siguiente agente

- Pipeline Fase 1 completo: URL -> evaluacion -> extraccion -> guia -> chat RAG.
- Embeddings y DB consistentes: modelo, dimension, RPC y metricas.
- Seguridad base activa: RLS + SSRF hardening + secretos fuera de codigo.
- Fase 2 paper con control fuerte:
  - HITL funcional
  - idempotencia real
  - reconciliacion hibrida
  - breakers activos
  - logs correlacionados
- Reporte diario con:
  - PnL
  - costo LLM
  - eventos de riesgo
  - divergencias de reconciliacion

## Riesgos residuales (no bloqueantes si se controlan)

1. Drift de APIs (Gemini/AI SDK/Binance) por cambios de proveedor.
2. Cambios de pricing de LLM/embeddings (impacto de costo).
3. Degradacion de calidad RAG si crece dataset sin recalibrar threshold.
4. Ruido de mercado que invalide reglas de paper trading en ciertos periodos.

## Regla de mantenimiento de este CODEX

- Cada cambio de version de:
  - Next.js
  - AI SDK
  - Gemini models
  - Binance endpoints
  debe gatillar reauditoria y actualizacion de `CODEX`.

