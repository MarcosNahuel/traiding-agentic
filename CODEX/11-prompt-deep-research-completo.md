# Prompt Completo - Deep Research

```text
Actua como investigador tecnico senior (arquitectura de sistemas, LLM apps, seguridad, trading systems y OSS intelligence).

## Contexto
Estoy evaluando y fortaleciendo este proyecto:
- Repo: traiding-agentic
- Documento base: docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md
- Carpeta de auditoria previa: CODEX/

Quiero una investigacion profunda para encontrar:
1) riesgos reales,
2) oportunidades de mejora,
3) insights accionables,
4) documentacion y repositorios fuente de alta calidad.

## Objetivo principal
Determinar si el plan es ejecutable y competitivo para un MVP institucional (research + RAG + trading simulado), y que cambios concretos deben hacerse para reducir riesgo y acelerar entrega.

## Reglas de investigacion (obligatorias)
1. Usa solo fuentes primarias/oficiales para validar hechos tecnicos criticos.
2. Incluye fecha exacta de consulta por fuente.
3. Si algo cambio recientemente (deprecations, endpoints, pricing), prioriza lo mas nuevo.
4. Si hay conflicto entre fuentes, explicitalo y propone resolucion.
5. No inventes datos ni "best practices" sin evidencia.
6. Separa claramente: hecho confirmado vs inferencia.
7. Todo hallazgo debe traer evidencia enlazada (URL directa).

## Areas a investigar (deep research)
### A) Stack y arquitectura
- Next.js/React/TypeScript/Tailwind/Vercel: compatibilidad real, limites de runtime y serverless.
- Patrones recomendados para jobs largos (queue/workers/background jobs).
- Riesgos de escalabilidad del diseno actual.

### B) AI stack (Vercel AI SDK + Gemini)
- Estado actual de APIs (modelos, embeddings, compatibilidad de metodos).
- Deprecaciones y fechas de sunset.
- Calidad/costo/rendimiento de modelos para:
  - extraccion estructurada,
  - sintesis,
  - chat RAG.

### C) RAG + pgvector
- Mejor estrategia de embeddings (modelo, dimensiones, costo, recall).
- HNSW vs IVFFlat para este caso.
- Diseno de chunking y retrieval (threshold, top-k, filtros metadata).
- Metricas objetivas para evaluar calidad del RAG.

### D) Seguridad y hardening
- SSRF y seguridad de ingestion de URLs/PDFs.
- Prompt injection y data exfiltration en agentes.
- RLS en Supabase (patrones minimos recomendados desde MVP).
- Gestion de secretos y controles de entorno.

### E) Binance y trading simulado
- Estado actual de Spot Testnet vs Futures Demo (REST/WS, auth, limitaciones).
- Riesgos de mezclar entornos.
- Guardrails obligatorios para evitar operaciones productivas por error.
- Diseno recomendado: MCP market-data + execution adapter determinista.

### F) MCP ecosystem (repositorios)
Auditar y comparar:
- forgequant/mcp-provider-binance
- TermiX-official/binance-mcp
- AnalyticAce/BinanceMCPServer
Y ademas repos core del stack:
- vercel/ai
- vercel/next.js
- supabase/supabase
- pgvector/pgvector
- googleapis/js-genai

Para cada repo:
- actividad reciente,
- mantenimiento,
- issues/riesgos,
- madurez para produccion,
- encaje real con este proyecto.

### G) Testing, observabilidad y operacion
- Que falta para tener pruebas confiables (unit/integration/e2e/contract).
- Que metricas instrumentar desde dia 1 (latencia, costo, errores, drift).
- Estrategia de rollback y gestion de incidentes.

### H) Benchmark de alternativas
- Proponer 2-3 alternativas por componente critico (embedding model, queue, MCP approach).
- Comparar tradeoffs: complejidad, costo, riesgo, time-to-market.

## Preguntas que debes responder si o si
1. El plan actual es GO, GO condicionado o NO-GO? Por que?
2. Cuales son los bloqueantes P0 hoy?
3. Que cambios tienen mayor ROI tecnico en 7 dias?
4. Que decisiones podrian romper el proyecto en produccion?
5. Que arquitectura recomiendas para integrar Binance con maxima seguridad operativa?
6. Que repos/implementaciones vale la pena adoptar o forkear y cuales descartar?

## Formato de salida (obligatorio)
1. Resumen ejecutivo (10-15 lineas).
2. Tabla de hallazgos P0 (riesgo, impacto, evidencia, accion).
3. Tabla de hallazgos P1/P2.
4. Matriz comparativa de repositorios.
5. Recomendacion arquitectonica final (diagrama textual + decisiones).
6. Plan de accion:
   - 48 horas,
   - 7 dias,
   - 30 dias.
7. Lista de decisiones pendientes con criterio para decidir.
8. Apendice de fuentes:
   - URL,
   - fecha de consulta,
   - tipo de fuente (oficial/repo/comunidad),
   - nivel de confianza (alto/medio/bajo).

## Estilo
- Escribe en espanol tecnico, directo y accionable.
- No uses relleno.
- Prioriza claridad y evidencia.
```

