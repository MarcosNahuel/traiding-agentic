# 01 - Validacion de fundamentos

## Resumen

El plan esta bien en arquitectura general, pero hay drift tecnico importante en APIs, modelos y endpoints de Binance. Se detectan riesgos que pueden frenar ejecucion real o generar comportamientos no deseados en produccion.

## Matriz de validacion

| Area | Referencia del plan | Estado | Evidencia externa | Impacto | Recomendacion |
|---|---|---|---|---|---|
| Stack base (Next/React/Tailwind) | `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:117` `:118` `:120` | Parcialmente valido | Next.js 16 release y docs oficiales; React 19 docs; Tailwind v4 docs | Base correcta, pero faltan constraints de runtime | Mantener stack y fijar versiones exactas + lockfile |
| Runtime Node | `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:112-144` | Falta requisito | `create-next-app` docs: Node.js `^20.9.0` o superior | CI/build pueden romper por version de Node | Agregar prerequisito explicito de Node y engines en `package.json` |
| Libreria Google JS | `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:128` | Desactualizado | Gemini API JS docs: `@google/generative-ai` esta deprecado a favor de `@google/genai` | Riesgo de deuda tecnica y migracion temprana | Eliminar `@google/generative-ai` del plan MVP si se usa `@ai-sdk/google` |
| Modelo Gemini usado | `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:510` `:680` `:802` `:956` `:1002` | Riesgo alto temporal | Pagina oficial de modelos deprecados: `gemini-2.0-flash` con deprecacion temprana 2026-02-05 | Riesgo de corte de servicio cercano o calidad inestable | Migrar ya a `gemini-2.5-flash` o `gemini-2.5-flash-lite` |
| API embeddings en AI SDK | `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:664` `:972` | Inconsistente con docs actuales | Provider docs de `@ai-sdk/google` usan `google.embedding('...')` | Implementacion puede no compilar segun version | Alinear snippets al API actual del SDK y fijar version |
| Costeo embeddings | `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:1073` | No validado / probable subestimacion | Pricing oficial Gemini: `gemini-embedding-001` en USD por 1M tokens | Presupuesto y forecast de costos incorrecto | Recalcular costos en plan con precios oficiales vigentes |
| SQL + pgvector | `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:322-324` | Mejorable | pgvector docs: HNSW suele mejor tradeoff; IVFFlat requiere tuning y entrenamiento con datos | Recall pobre y latencia no estable con dataset chico | Empezar sin indice o con HNSW; si IVFFlat, tunear `lists` por volumen real |
| RPC similarity fija | `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:1016-1041` | Riesgo medio | Buenas practicas RAG: threshold depende del embedding/modelo/dominio | Recuperacion pobre o demasiado ruido | Calibrar threshold por evaluacion offline (nDCG/precision@k) |
| Reader Agent snippet | `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:697-701` | Error de codigo | `extraction_id: extractionId` sin definicion previa en snippet | Falla directa al guardar estrategias | Guardar insert de extraccion con retorno `id` y usar ese valor |
| Truncamiento de contenido | `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:513` `:683` | Riesgo funcional | Se corta entrada en `slice(15000)` y `slice(30000)` | Perdida de evidencia y extracciones incompletas | Procesar por secciones/chunks y fusionar resultados |
| Binance Spot WS endpoint | `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:1090` | Incorrecto | Spot Testnet docs: WS base `wss://stream.testnet.binance.vision` | Conexion WS puede fallar | Cambiar endpoint WS del plan |
| Futures en test/demo | `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:1086-1135` | Incompleto | Binance futures docs + comunidad dev: migracion a Demo Trading con `https://demo-fapi.binance.com` | Si objetivo es perps, flujo actual no sirve tal cual | Separar Spot Testnet y Futures Demo desde diseno |
| "Edge functions para API routes" | `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:1227` | Confuso | Next Route Handlers y Vercel function duration docs | Jobs largos (embedding/extraccion) pueden cortar por timeout | Mover procesos largos a job queue/worker |
| Seguridad fetch URLs | `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:551` | Gap critico | Practica estandar seguridad backend | Riesgo SSRF e ingest de contenido malicioso | Allowlist/denylist, validacion DNS/IP, timeouts, limites de tamano |
| RLS "si se agrega auth" | `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:1171` | Riesgo medio | Supabase RLS docs recomiendan habilitar politicas por tabla | Exposicion accidental de datos | Definir RLS desde MVP (aunque sea single-tenant) |

## Fortalezas confirmadas

- Separacion de agentes por responsabilidad: buena base para observabilidad y evolucion.
- Restriccion explicita de risk manager determinista: decision correcta para controlar riesgo operativo.
- Esquema inicial de tablas cubre pipeline research -> strategy -> guide de forma trazable.

## Riesgos P0 (bloqueantes para build confiable)

1. Migrar modelos/SDK de Gemini a opciones vigentes y API actual.
2. Corregir endpoints Binance (Spot WS y estrategia Futures Demo).
3. Resolver snippet roto de `extractionId` y estrategia de truncamiento de textos.
4. Definir ejecucion async para tareas largas fuera de request-response.
5. Endurecer fetcher contra SSRF.
6. Recalibrar costos reales de embedding.
7. Corregir versionado y constraints de guia (`version` unica + control de concurrencia).
