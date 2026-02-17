# 04 - Opinion tecnica sobre el plan maestro

## Opinion directa

El plan maestro es bueno como blueprint de producto, pero todavia no esta listo para ejecucion "sin friccion". Hay varios detalles tecnicos de alto impacto (APIs, endpoints y operacion asincrona) que deben corregirse antes de iniciar construccion fuerte.

Veredicto: `GO condicionado`.

- GO para arquitectura y enfoque por agentes.
- Condicionado a cerrar backlog P0 antes de week 1 completa.

## Lo mejor del plan

1. Scope MVP bien acotado (`research -> synthesis -> guide`) antes de trading real.
2. Enfoque de riesgo determinista separado del LLM.
3. Modelo de datos suficientemente expresivo para trazabilidad.
4. Roadmap por semanas claro y accionable.

## Lo que hoy lo frena (P0)

1. Dependencias/modelos con drift:
- `@google/generative-ai` deprecado.
- `gemini-2.0-flash` en ventana de deprecacion.
- API de embedding en snippets no alineada a docs actuales.

2. Binance endpointing incompleto:
- WS spot testnet mal apuntado en snippet.
- Futures demo necesita base distinta (`demo-fapi`) y router por entorno.

3. Ejecucion larga en request-response:
- Reader/Synthesis con embeddings + parsing deben correr como jobs async.

4. Seguridad de ingestion:
- Fetch de URL sin controles SSRF ni limites fuertes de payload.

5. Bug de snippet:
- `extractionId` no definido al insertar estrategias.

6. Costeo y supuestos economicos:
- Numero de costo de embeddings no coincide con pricing oficial actual.

7. Versionado de guias:
- Falta constraint unico para `version` y proteccion de concurrencia.

## Backlog recomendado

### P0 (hacer primero)

1. Actualizar stack IA:
- fijar `@ai-sdk/google` en version concreta
- migrar modelo base a `gemini-2.5-flash` (o `-lite`)
- corregir API embedding en snippets

2. Corregir Binance:
- endpoint WS spot testnet
- router de entorno demo futures vs spot testnet

3. Mover pipeline de procesamiento a background jobs.

4. Endurecer fetcher:
- validacion URL
- bloqueo IP privadas y metadata endpoints
- timeout + max bytes + content-type whitelist

5. Corregir bug `extractionId` y asegurar transaccion DB.

6. Agregar constraints DB:
- `UNIQUE(version)` en `trading_guides`
- idempotency key para corridas de pipeline

### P1 (inmediatamente despues)

1. Evaluacion RAG offline para calibrar `match_threshold`.
2. Reemplazar IVFFlat fijo por estrategia index-aware (HNSW o tuning por volumen).
3. Instrumentar observabilidad de costos y latencias por agente.

### P2 (endurecimiento)

1. RLS desde MVP, aunque sea single-tenant.
2. Suite de pruebas contractuales para prompts JSON.
3. Plan de rollback de versiones de guia y modelos.

## Ajuste recomendado al roadmap

- Semana 1: sumar "hardening P0" como bloque formal.
- Semana 2: source/reader sobre cola async, no sync APIs.
- Semana 3: synthesis + dashboard + metrica de calidad RAG.
- Semana 4: MCP read-only + adapter de ejecucion demo (si aplica perps).

## Resultado esperado tras ajustes

Con estos cambios, el plan queda en un estado tecnicamente ejecutable para MVP institucional, con menor probabilidad de bloqueos por cambios de proveedor, timeouts serverless y errores de entorno Binance.
