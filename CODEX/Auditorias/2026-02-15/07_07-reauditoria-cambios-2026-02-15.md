# 07 - Reauditoria tras cambios (2026-02-15)

Documento auditado: `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md` (1177 lineas, ultima edicion 2026-02-15 15:51)

## Resultado ejecutivo

Estado general: `MEJORO FUERTE`, pero no queda 100% cerrado.

- P0 cerrados respecto a la auditoria anterior: 10
- P0 nuevos/reabiertos detectados: 2
- P1 pendientes: 4
- Veredicto: `GO condicionado` (cerrar 2 P0 antes de implementacion)

## Cambios validados como correctos

1. Migracion de provider
- Antes: `@google/generative-ai`
- Ahora: `@ai-sdk/google` (`docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:128`)
- Estado: Correcto.

2. Modelo principal actualizado
- Antes: `gemini-2.0-flash`
- Ahora: `gemini-2.5-flash` (`...:511`, `...:681`, `...:809`, `...:963`, `...:1009`)
- Estado: Correcto.

3. API de embedding en AI SDK v6
- Antes: `textEmbeddingModel(...)`
- Ahora: `google.embedding(...)` (`...:665`, `...:979`)
- Estado: Correcto segun docs AI SDK v6.

4. Bug de `extractionId`
- Antes: variable no definida.
- Ahora: captura de ID con `.select('id').single()` y uso posterior (`...:687-701`, `...:707`)
- Estado: Corregido en el snippet.

5. pgvector index
- Antes: IVFFlat fijo.
- Ahora: HNSW (`...:322-325`)
- Estado: Mejora razonable para volumen inicial.

6. Constraint de versionado
- `version INTEGER NOT NULL UNIQUE` en `trading_guides` (`...:337`)
- Estado: Corregido.

7. Binance Spot WS
- Antes: endpoint legacy incorrecto.
- Ahora: `wss://stream.testnet.binance.vision/ws/...` (`...:1106`)
- Estado: Correcto.

8. Separacion de entornos Binance
- Tabla Spot Testnet vs Futures Demo (`...:1095-1099`)
- Estado: Correcto conceptualmente.

9. Seguridad SSRF + RLS declaradas
- SSRF hardening explicito (`...:1186`)
- RLS desde MVP (`...:1187`)
- Estado: Correcto como criterio de arquitectura.

10. Jobs async para procesos largos
- Declarado en deploy/roadmap (`...:1255`, `...:1283`, `...:1288`)
- Estado: Correcto como directriz.

## P0 abiertos (nuevos/reabiertos)

1. Embedding model desactualizado en el plan
- Actualmente el plan sigue usando `text-embedding-004` (`...:665`, `...:979`, `...:1079`).
- En deprecations oficiales de Gemini figura shutdown en `2026-01-14`.
- Impacto: riesgo real de falla de embeddings en runtime.
- Accion: migrar default a `gemini-embedding-001` y ajustar dim de vector (3072) o setear `outputDimensionality: 768/1024` explicitamente si se requiere compatibilidad.

2. Registro de auditoria interno marca "Aplicado" para costo embedding, pero sin migrar modelo
- El item #13 del registro (`...:1411`) declara correccion de costos, pero la eleccion tecnica base del embedding sigue en modelo ya retirado.
- Impacto: inconsistencias de presupuesto y de disponibilidad.
- Accion: actualizar secciones 10/11 + SQL schema (`VECTOR(...)`) + checklist de migracion.

## P1 pendientes

1. `match_threshold` fijo en `0.7` sin calibracion empirica (`...:986`, `...:1025`, `...:1414`).
2. Truncamiento de contexto sigue presente (`rawContent.slice(0,15000)` y `fullText.slice(0,30000)`) (`...:514`, `...:684`).
3. Synthesis Agent puede exceder contexto al serializar arrays completos en prompt (`...:815-819`).
4. RLS aparece como principio, pero faltan politicas SQL concretas en seccion de esquema.

## Decision MCP Binance (revalidada)

- Sigue vigente la recomendacion previa:
  - MCP para market data/read-only al inicio.
  - Adapter determinista separado para ejecucion de ordenes.
- Confirmado en docs oficiales de futures:
  - REST demo: `https://demo-fapi.binance.com`
  - WS demo: `wss://fstream.binancefuture.com`
- Conclusión: incorporar MCP SI, pero con router estricto por entorno y kill-switch global.

## Acciones inmediatas (orden sugerido)

1. Migrar embeddings a `gemini-embedding-001` y ajustar `VECTOR(dim)` + RPC.
2. Reescribir seccion de costos con modelo vigente y estimaciones por 1M tokens.
3. Agregar estrategia de "map-reduce extraction" para evitar truncamiento.
4. Definir politicas RLS minimas en migraciones SQL.
