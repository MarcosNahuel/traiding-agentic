# Fase 1: Research Trading Agent — Plan de Implementacion

**Proyecto:** traiding-agentic
**Fecha:** 2026-02-15
**Duracion:** Semanas 1-4
**Estado:** Aprobado, listo para build

---

## 1. Objetivo

Construir un sistema de 3 agentes de IA que recopile, analice y sintetice conocimiento de trading desde papers academicos, generando una "Guia Maestra" de trading. Incluye dashboard web y chat con RAG.

## 2. Stack

| Capa | Tecnologia | Version |
|---|---|---|
| Framework | Next.js | 16 |
| UI | React 19 + Tailwind CSS 4 | latest |
| LLM | Gemini via @ai-sdk/google | gemini-2.5-flash |
| Embeddings | gemini-embedding-001 | 1024 dims (outputDimensionality) |
| DB | Supabase PostgreSQL + pgvector | latest |
| Hosting | Vercel (serverless) | Free/Pro |
| Runtime | Node.js >= 20.9.0 | fijar en engines |
| Package manager | pnpm | latest |
| Testing | Vitest (unit) + Playwright (E2E) | latest |

## 3. Arquitectura

```
Usuario (Web)
    |
Next.js 16 (Vercel)
  - Dashboard (sources, strategies, guide, chat)
  - API Routes (serverless functions)
    |
    +--- Source Agent (evalua fuentes, score 1-10)
    +--- Reader Agent (extrae estrategias, crea embeddings)
    +--- Synthesis Agent (genera Guia Maestra versionada)
    |
    +--- Gemini 2.5 Flash (LLM)
    +--- Supabase (PostgreSQL + pgvector)
```

**Principios:**
- Serverless-first (todo en Vercel)
- Agentes desacoplados (se comunican via DB)
- LLM decide estrategia, codigo impone limites
- Toda accion se loguea (event sourcing basico)
- Guias inmutables y versionadas

## 4. Modelo de Datos

### 4.1 Tablas principales

| Tabla | Proposito |
|---|---|
| `sources` | Fuentes evaluadas (URL, scores, status workflow) |
| `paper_extractions` | Info estructurada extraida de cada paper |
| `strategies_found` | Estrategias individuales con backtest results |
| `paper_chunks` | Chunks con embeddings VECTOR(1024) para RAG |
| `trading_guides` | Guias maestras versionadas (version UNIQUE) |
| `agent_logs` | Logs inmutables de toda accion de agentes |
| `chat_messages` | Historial de conversaciones |

### 4.2 Indices clave
- `paper_chunks.embedding`: HNSW (vector_cosine_ops, m=16, ef_construction=64)
- RLS habilitado en todas las tablas desde MVP
- Politicas service_role_full_access para backend

### 4.3 RPC
- `match_chunks(query_embedding VECTOR(1024), match_threshold, match_count)` — busqueda vectorial

## 5. Agentes

### 5.1 Source Agent
- **Input:** URL de paper/articulo
- **Proceso:** Evalua con Gemini (relevance, credibility, applicability scores 1-10)
- **Output:** Status approved (score >= 6) o rejected
- **Modelo:** gemini-2.5-flash via generateObject() con Zod schema
- **Truncamiento:** rawContent.slice(0, 15000)

### 5.2 Reader Agent
- **Input:** Source aprobada
- **Proceso:**
  1. Fetch contenido completo
  2. Chunk texto (~500 tokens, overlap 50)
  3. Generar embeddings (gemini-embedding-001, 1024 dims, providerOptions)
  4. Almacenar chunks en pgvector
  5. Extraer estrategias estructuradas con Gemini
  6. Guardar extraction + strategies (con extractionId correcto)
- **Modelo:** gemini-2.5-flash
- **Cola async:** Jobs largos no en request-response
- **NOTA P1:** Implementar map-reduce para papers > 30k chars

### 5.3 Synthesis Agent
- **Input:** Todas las estrategias + extracciones
- **Proceso:** Cruza informacion, resuelve contradicciones, rankea por evidencia
- **Output:** Trading Guide versionada con:
  - Estrategia principal + secundarias
  - Mapa de condiciones de mercado
  - Lista de "NO hacer"
  - Parametros de riesgo sugeridos
  - System prompt para trading bot
- **Modelo:** gemini-2.5-flash

## 6. API Routes

```
# Sources
POST   /api/sources              - Agregar fuente (body: {url})
GET    /api/sources              - Listar (?status=approved&sort=score)
GET    /api/sources/[id]         - Detalle
POST   /api/sources/[id]/evaluate - Trigger Source Agent
POST   /api/sources/[id]/process  - Trigger Reader Agent
DELETE /api/sources/[id]         - Eliminar

# Strategies
GET    /api/strategies           - Listar (?type=momentum&market=btc)
GET    /api/strategies/[id]      - Detalle
GET    /api/strategies/stats     - Estadisticas

# Guides
POST   /api/guides/generate      - Trigger Synthesis Agent
GET    /api/guides/current        - Guia actual
GET    /api/guides/[version]      - Por version
GET    /api/guides/history        - Todas las versiones
GET    /api/guides/system-prompt  - Solo el system prompt

# Chat (RAG)
POST   /api/chat                 - Mensaje (streaming)
GET    /api/chat/history         - Historial

# Pipeline
POST   /api/pipeline/run         - Ejecutar pipeline completo
GET    /api/pipeline/status      - Estado del pipeline

# Stats
GET    /api/stats                - Estadisticas del sistema
```

## 7. Frontend

### Paginas
| Ruta | Contenido |
|---|---|
| `/` | Overview dashboard (stats, ultimo activity) |
| `/sources` | Lista de fuentes con scores, filtros |
| `/sources/[id]` | Detalle: scores, estrategias extraidas, chunks |
| `/sources/new` | Formulario para agregar URL |
| `/strategies` | Lista de estrategias con filtros por tipo/mercado |
| `/strategies/[id]` | Detalle con backtest results |
| `/guide` | Guia maestra actual (render markdown) |
| `/guide/history` | Historial de versiones |
| `/chat` | Chat con RAG (useChat de Vercel AI SDK) |

### Stack UI
- Tailwind CSS 4 para styling
- SWR para data fetching + cache
- useChat() de Vercel AI SDK para streaming chat

## 8. RAG Pipeline

```
Pregunta del usuario
    → Generar embedding (gemini-embedding-001, 1024 dims)
    → Buscar chunks similares (pgvector, cosine > 0.7, top 5)
    → Agregar como contexto al prompt
    → Gemini responde con conocimiento de papers
```

- **Embedding:** gemini-embedding-001 via google.embedding() + providerOptions
- **Index:** HNSW (m=16, ef_construction=64)
- **Chunk size:** 500 tokens, overlap 50
- **P1:** Calibrar match_threshold con evaluacion offline (precision@k)

## 9. Seguridad

1. API keys solo en env vars del servidor
2. LLM nunca controla parametros de riesgo
3. Proteccion SSRF en fetcher (allowlist, bloqueo IPs privadas, timeouts, content-type whitelist)
4. RLS habilitado desde MVP en todas las tablas
5. Logs inmutables de toda accion
6. generateObject() con Zod schema (output estructurado, no free text)

## 10. Testing

### Unit (Vitest)
- Chunking algorithm
- Schema validation
- Indicator calculations (para Fase 2)

### Integration
- Source Agent: evalua paper mock, verifica scores
- Reader Agent: extrae estrategia de texto mock
- Synthesis Agent: genera guia desde estrategias mock
- API routes: CRUD completo

### E2E (Playwright)
- Agregar fuente desde UI
- Ver estrategias extraidas
- Chatear con el agente
- Generar guia

## 11. Deploy

- **Vercel:** Push to main = deploy automatico, preview en PRs
- **Supabase:** Migrations con CLI, seed data para dev
- **CI:** Lint → Type check → Unit tests → Build → Deploy preview
- **Nota:** Procesos largos (embedding/extraccion) via background jobs, no request-response

## 12. Roadmap

### Semana 1: Foundation + Hardening P0
- [ ] Crear proyecto Next.js 16
- [ ] Fijar engines node >= 20.9.0
- [ ] Configurar Tailwind CSS 4
- [ ] Setup Supabase (tablas + pgvector + RLS)
- [ ] Ejecutar migrations SQL (HNSW + UNIQUE constraints)
- [ ] Configurar Vercel AI SDK + gemini-2.5-flash
- [ ] Implementar fetcher seguro (SSRF protection)
- [ ] Crear estructura de carpetas
- [ ] Setup cola async para jobs largos
- [ ] Deploy inicial a Vercel

### Semana 2: Source Agent + Reader Agent
- [ ] Implementar Source Agent con fetcher seguro
- [ ] Implementar Reader Agent sobre cola async
- [ ] Implementar chunking + embeddings (pgvector)
- [ ] API routes: sources CRUD + evaluate + process
- [ ] Cargar 5-10 papers iniciales de prueba
- [ ] Verificar pipeline end-to-end

### Semana 3: Synthesis Agent + Dashboard
- [ ] Implementar Synthesis Agent
- [ ] API routes: guides generate + current + history
- [ ] Dashboard: Overview, Sources, Strategies, Guide pages
- [ ] Chat: implementar con useChat() + RAG

### Semana 4: Polish + Preparar Fase 2
- [ ] Re-analisis automatico (cron/webhook)
- [ ] Mejorar UI (loading states, error handling)
- [ ] Testing (unit + integration)
- [ ] Documentacion
- [ ] Preparar estructura para Fase 2

## 13. Estructura de Archivos

```
traiding-agentic/
  app/
    layout.tsx
    page.tsx                          # Overview dashboard
    globals.css
    sources/
      page.tsx                        # Sources list
      [id]/page.tsx                   # Source detail
      new/page.tsx                    # Add source
    strategies/
      page.tsx                        # Strategies list
      [id]/page.tsx                   # Strategy detail
    guide/
      page.tsx                        # Current guide
      history/page.tsx                # Guide history
    chat/
      page.tsx                        # Chat interface
    api/
      sources/
        route.ts                      # GET list, POST create
        [id]/
          route.ts                    # GET detail, DELETE
          evaluate/route.ts           # POST trigger evaluation
          process/route.ts            # POST trigger processing
      strategies/
        route.ts                      # GET list
        [id]/route.ts                 # GET detail
        stats/route.ts                # GET statistics
      guides/
        route.ts                      # GET history
        generate/route.ts             # POST generate
        current/route.ts              # GET current
        [version]/route.ts            # GET by version
        system-prompt/route.ts        # GET system prompt
      chat/
        route.ts                      # POST message (streaming)
        history/route.ts              # GET history
      pipeline/
        run/route.ts                  # POST run full pipeline
        status/route.ts               # GET pipeline status
      stats/
        route.ts                      # GET system stats
  lib/
    supabase.ts                       # Supabase client
    ai.ts                             # Vercel AI SDK setup
    agents/
      source-agent.ts                 # Source evaluation logic
      reader-agent.ts                 # Paper extraction logic
      synthesis-agent.ts              # Guide generation logic
      prompts.ts                      # All system prompts
    utils/
      chunking.ts                     # Text chunking for RAG
      fetcher.ts                      # URL content fetcher (SSRF-safe)
  components/
    ui/                               # Shared UI components
    sources/                          # Source-specific components
    strategies/                       # Strategy-specific components
    guide/                            # Guide-specific components
    chat/                             # Chat components
    dashboard/                        # Dashboard widgets
  supabase/
    migrations/
      001_initial_schema.sql          # All tables
      002_pgvector_setup.sql          # pgvector extension + functions
    seed.sql                          # Development seed data
  public/
  .env.local
  .env.example
  next.config.ts
  package.json
  tsconfig.json
  tailwind.config.ts
```

## 14. Definition of Done (Fase 1)

- [ ] 3 agentes funcionales (source, reader, synthesis)
- [ ] Pipeline end-to-end: URL → evaluacion → extraccion → guia maestra
- [ ] RAG operativo: chat responde con contexto de papers
- [ ] Dashboard con todas las paginas funcionales
- [ ] Al menos 5 papers procesados exitosamente
- [ ] Al menos 1 guia maestra generada
- [ ] Tests unitarios e integracion pasando
- [ ] Deploy en Vercel funcionando
- [ ] RLS habilitado en todas las tablas
- [ ] Fetcher con proteccion SSRF

## 15. Auditorias aplicadas

Este plan incorpora correcciones de 3 rondas de auditoria CODEX:

| Ronda | Correcciones clave |
|---|---|
| 1 | @google/generative-ai → @ai-sdk/google, gemini-2.0-flash → 2.5-flash, WS Binance fix, HNSW, RLS, SSRF, extractionId bug |
| 2 | text-embedding-004 → gemini-embedding-001, VECTOR(768) → 1024, providerOptions syntax, RLS policies, cost tracking |
| 3 | Fase 2 completa agregada como secciones separadas (no afecta Fase 1) |

Fuentes de auditoria verificadas:
- Gemini deprecations: https://ai.google.dev/gemini-api/docs/deprecations
- AI SDK v6: https://ai-sdk.dev/docs/migration-guides/migration-guide-6-0
- AI SDK Google embeddings: https://ai-sdk.dev/providers/ai-sdk-providers/google-generative-ai
- Binance Spot Testnet: https://developers.binance.com/docs/binance-spot-api-docs/testnet/web-socket-streams
- pgvector HNSW: https://github.com/pgvector/pgvector
- Supabase RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
