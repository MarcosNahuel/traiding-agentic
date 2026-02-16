# 08 - Prompt maestro para Deep Research

Usa este prompt tal cual para ejecutar una investigacion profunda y verificable:

```text
Actua como auditor tecnico senior (arquitectura + seguridad + trading systems + LLM apps).

Contexto del proyecto:
- Repo: traiding-agentic
- Documento principal: docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md
- Objetivo: validar si el plan es ejecutable para MVP institucional (research + RAG + trading simulado), detectar riesgos y proponer correcciones priorizadas.

Instrucciones obligatorias:
1) Lee el plan completo y crea una matriz de validacion:
   - Afirmacion del plan
   - Evidencia tecnica (fuente primaria)
   - Estado (Valido / Parcial / Invalido)
   - Riesgo (P0/P1/P2)
   - Correccion recomendada
2) Verifica con fuentes oficiales y actuales (no blogs secundarios) para:
   - Next.js (version, runtime, route handlers, limitaciones serverless)
   - Vercel AI SDK + @ai-sdk/google (sintaxis vigente de modelos y embeddings)
   - Gemini deprecations/pricing/model lifecycle
   - Supabase + Postgres + pgvector (indices HNSW/IVFFlat, RLS)
   - Binance Spot Testnet y Futures Demo (REST/WS endpoints, cambios recientes)
3) Audita repos fuente relevantes:
   - vercel/ai, vercel/next.js, pgvector/pgvector, supabase/supabase
   - MCP Binance candidatos (forgequant/mcp-provider-binance, TermiX-official/binance-mcp, AnalyticAce/BinanceMCPServer)
   Para cada repo: actividad, madurez, riesgos operativos, cobertura funcional para el caso de uso.
4) Evalua coherencia interna del plan:
   - snippets compilables o con errores
   - consistencia de modelos/dimensiones/vector schema
   - escalabilidad de prompts/context windows
   - seguridad de ingestion (SSRF, prompt injection)
   - control de riesgo determinista
5) Entrega un veredicto final:
   - GO / GO condicionado / NO-GO
   - lista de bloqueantes P0
   - backlog P1/P2
   - roadmap corregido por semanas
6) Incluye una seccion especifica: "Incorporacion MCP Binance"
   - opcion recomendada para arrancar en demo
   - arquitectura propuesta (MCP read-only + execution adapter)
   - guardrails obligatorios para evitar operaciones en produccion
7) Usa fechas absolutas y detecta deprecaciones con fecha exacta.
8) Si una afirmacion no puede comprobarse, dilo explicitamente.
9) Entrega links directos de todas las fuentes usadas.

Formato de salida requerido:
- Resumen ejecutivo (10-15 lineas)
- Hallazgos P0 (tabla)
- Hallazgos P1/P2 (tabla)
- Auditoria de repos (tabla comparativa)
- Recomendacion MCP Binance (decision + arquitectura)
- Plan de accion 7 dias
- Apendice de fuentes (URL + fecha de consulta)
```

## Variante corta (si quieres una version rapida)

```text
Audita tecnicamente el archivo docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md con evidencia oficial y actualizada. Entrega: 1) hallazgos P0/P1/P2, 2) validacion de stack AI SDK/Gemini/Supabase/Binance, 3) recomendacion concreta para integrar MCP Binance en demo con guardrails. Usa solo fuentes primarias y agrega links.
```
