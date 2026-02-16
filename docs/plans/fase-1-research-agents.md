# Fase 1: Research Agents + Dashboard + Chat RAG

**Proyecto:** traiding-agentic
**Duracion:** Semanas 2-4 (3 semanas)
**Prerequisitos:** Fase 0 completa (gate de salida aprobado)
**Estado:** Plan final validado
**Fecha:** 2026-02-15

---

## 1. Objetivo

Construir el pipeline completo de investigacion: 3 agentes de IA que evaluan, extraen y sintetizan conocimiento de trading desde papers academicos. Incluye dashboard web para gestion y chat conversacional con RAG.

## 2. Decisiones Tecnicas Cerradas

| Decision | Valor | Origen |
|---|---|---|
| Agentes | Source, Reader, Synthesis | Plan tecnico |
| Output LLM | generateObject() con Zod schema | CODEX - anti prompt injection |
| Chunking | ~500 tokens, overlap 50 | Plan tecnico |
| RAG threshold | 0.7 inicial, calibrar post-MVP con precision@k | CODEX P1 |
| Truncamiento | slice(15000) Source, slice(30000) Reader + nota P1 map-reduce | CODEX |
| Chat streaming | useChat() de Vercel AI SDK | Plan tecnico |
| Data fetching | SWR 2.x | Plan tecnico |

## 3. Entregables por Semana

### Semana 2: Source Agent + Reader Agent

#### 3.1 Source Agent

- [ ] Implementar `lib/agents/source-agent.ts`
- [ ] System prompt completo (criterios 1-10: relevancia, credibilidad, aplicabilidad)
- [ ] Schema Zod para evaluacion (sourceEvaluationSchema)
- [ ] Flujo: URL → fetch con fetcher SSRF-safe → evaluacion con Gemini → update status en DB
- [ ] Logging en agent_logs (tokens, costo, duracion, reasoning)
- [ ] Score >= 6: approved, < 6: rejected con razon

**Implementacion core:**

```typescript
// lib/agents/source-agent.ts
import { generateObject } from 'ai';
import { google } from '@/lib/ai';
import { z } from 'zod';

export async function evaluateSource(sourceId: string, url: string, rawContent: string) {
  const result = await generateObject({
    model: google('gemini-2.5-flash'),
    schema: sourceEvaluationSchema,
    system: SOURCE_AGENT_SYSTEM_PROMPT,
    prompt: `Evalua esta fuente:\nURL: ${url}\n\nContenido:\n${rawContent.slice(0, 15000)}`,
  });
  // Update source in DB + log
}
```

#### 3.2 Reader Agent

- [ ] Implementar `lib/agents/reader-agent.ts`
- [ ] System prompt para extraccion estructurada de estrategias
- [ ] Schema Zod para extraccion (extractionSchema)
- [ ] Chunking: `lib/utils/chunking.ts` (~500 tokens, overlap 50, split por headers/parrafos/oraciones)
- [ ] Embedding por chunk via Vercel Background Function:
  ```typescript
  const { embedding } = await embed({
    model: google.embedding('gemini-embedding-001'),
    value: chunk.content,
    providerOptions: { google: { outputDimensionality: 1024 } },
  });
  ```
- [ ] Guardar chunks en pgvector
- [ ] Extraccion estructurada con Gemini (estrategias, insights, warnings)
- [ ] Guardar extraction + strategies individuales (con extractionId correcto via `.select('id').single()`)
- [ ] NOTA P1: papers > 30k chars → registrar warning, implementar map-reduce post-MVP

**Flujo del Reader Agent (como Background Function):**

```
Source aprobada
  → Trigger Background Function
  → Fetch contenido completo
  → Chunk texto (~500 tokens, overlap 50)
  → Para cada chunk: generar embedding + guardar en pgvector
  → Extraccion estructurada con Gemini (estrategias, insights)
  → Guardar paper_extractions + strategies_found
  → Update source status → 'processed'
  → Log en agent_logs
```

#### 3.3 API Routes Semana 2

- [ ] `POST /api/sources` — Crear fuente (body: {url})
- [ ] `GET /api/sources` — Listar fuentes (?status=approved&sort=score)
- [ ] `GET /api/sources/[id]` — Detalle de fuente
- [ ] `POST /api/sources/[id]/evaluate` — Trigger Source Agent
- [ ] `POST /api/sources/[id]/process` — Trigger Reader Agent (Background Function)
- [ ] `DELETE /api/sources/[id]` — Eliminar fuente

#### 3.4 Validacion Semana 2

- [ ] Cargar 5-10 papers/articulos iniciales de prueba
- [ ] Verificar pipeline end-to-end: URL → evaluacion → extraccion → chunks en pgvector
- [ ] Verificar que sources rechazadas tienen razon clara
- [ ] Verificar que strategies_found tiene datos estructurados correctos

---

### Semana 3: Synthesis Agent + Dashboard

#### 3.5 Synthesis Agent

- [ ] Implementar `lib/agents/synthesis-agent.ts`
- [ ] System prompt para sintesis (cruzar info, resolver contradicciones, rankear)
- [ ] Schema Zod para guia (tradingGuideSchema)
- [ ] Versionado atomico: nueva guia = nuevo registro con version incremental
- [ ] Output: estrategia principal + secundarias + mapa condiciones + avoid list + risk params + system prompt para bot
- [ ] NOTA P1: control de contexto → no serializar arrays completos, usar top-N + resumen por lotes

**Implementacion core:**

```typescript
// lib/agents/synthesis-agent.ts
export async function generateTradingGuide() {
  // 1. Fetch strategies + extractions (top-N por confidence)
  // 2. Get last guide version
  // 3. Generate with Gemini via generateObject
  // 4. Save guide with version = lastVersion + 1
  // 5. Log en agent_logs
}
```

#### 3.6 API Routes Semana 3

- [ ] `GET /api/strategies` — Listar (?type=momentum&market=btc)
- [ ] `GET /api/strategies/[id]` — Detalle
- [ ] `GET /api/strategies/stats` — Estadisticas
- [ ] `POST /api/guides/generate` — Trigger Synthesis Agent
- [ ] `GET /api/guides/current` — Guia actual
- [ ] `GET /api/guides/[version]` — Por version
- [ ] `GET /api/guides/history` — Todas las versiones
- [ ] `GET /api/guides/system-prompt` — Solo system prompt generado
- [ ] `GET /api/stats` — KPIs generales del sistema

#### 3.7 Dashboard Frontend

**Pagina Overview (`/`):**
- [ ] Cards: total fuentes (aprobadas/rechazadas/pendientes), total estrategias, version guia, ultimo update
- [ ] Tabla: ultimas 5 acciones de agentes (de agent_logs)

**Pagina Sources (`/sources`):**
- [ ] Tabla: titulo, tipo, score, tags, status, acciones
- [ ] Filtros por status, tipo, score
- [ ] Boton "Agregar URL" → modal
- [ ] Acciones: Evaluar, Procesar, Ver detalle, Eliminar

**Pagina Source Detail (`/sources/[id]`):**
- [ ] Scores detallados, reasoning, tags
- [ ] Estrategias extraidas de este paper
- [ ] Status workflow

**Pagina Strategies (`/strategies`):**
- [ ] Tabla: nombre, tipo, timeframe, indicadores, confianza, paper origen
- [ ] Filtros por tipo, mercado, confianza
- [ ] Click para ver detalle con entry/exit rules y backtest results

**Pagina Guide (`/guide`):**
- [ ] Render markdown de guia actual
- [ ] Sidebar: version, fuentes usadas, confianza, fecha
- [ ] Boton "Re-generar guia"
- [ ] Tabs: Full Guide | System Prompt | Historial

---

### Semana 4: Chat RAG + Polish

#### 3.8 Chat con RAG

- [ ] Implementar `POST /api/chat` con streaming (streamText)
- [ ] Implementar `GET /api/chat/history`
- [ ] Pipeline RAG:
  1. Embedding de la pregunta (gemini-embedding-001, 1024 dims)
  2. Buscar chunks similares (pgvector, cosine > 0.7, top 5)
  3. Cargar guia maestra actual como contexto adicional
  4. Gemini responde con conocimiento de papers + guia
- [ ] Frontend: pagina `/chat` con useChat() de Vercel AI SDK
- [ ] Guardar mensajes en chat_messages

**Implementacion chat route:**

```typescript
// app/api/chat/route.ts
export async function POST(req: Request) {
  const { messages } = await req.json();
  const lastMessage = messages[messages.length - 1].content;

  // 1. Embedding de pregunta
  const { embedding } = await embed({
    model: google.embedding('gemini-embedding-001'),
    value: lastMessage,
    providerOptions: { google: { outputDimensionality: 1024 } },
  });

  // 2. Buscar chunks similares
  const { data: relevantChunks } = await supabase.rpc('match_chunks', {
    query_embedding: embedding,
    match_threshold: 0.7,
    match_count: 5,
  });

  // 3. Cargar guia actual
  const { data: guide } = await supabase
    .from('trading_guides')
    .select('full_guide_markdown')
    .order('version', { ascending: false })
    .limit(1)
    .single();

  // 4. Stream response con contexto
  const result = streamText({
    model: google('gemini-2.5-flash'),
    system: `...contexto de guia + chunks...`,
    messages,
  });

  return result.toDataStreamResponse();
}
```

#### 3.9 Pipeline Completo

- [ ] `POST /api/pipeline/run` — Ejecutar pipeline completo (evaluate → process → synthesize)
- [ ] `GET /api/pipeline/status` — Estado del pipeline
- [ ] El pipeline corre como secuencia de Background Functions

#### 3.10 Polish

- [ ] Loading states en todas las paginas
- [ ] Error handling (toast notifications, error boundaries)
- [ ] Responsive design basico
- [ ] Empty states (cuando no hay fuentes, estrategias, etc.)
- [ ] Confirmacion antes de eliminar fuentes
- [ ] Indicadores de progreso para operaciones async (evaluando, procesando, generando)

#### 3.11 Testing

**Unit Tests (Vitest):**
- [ ] Chunking algorithm: split correcto por headers/parrafos, overlap, metadata
- [ ] Schema validation: Zod schemas de los 3 agentes
- [ ] Fetcher: URLs validas pasan, URLs peligrosas se bloquean

**Integration Tests:**
- [ ] Source Agent: evalua paper mock, verifica scores y decision
- [ ] Reader Agent: extrae estrategia de texto mock, verifica estructura
- [ ] Synthesis Agent: genera guia desde estrategias mock, verifica version
- [ ] API routes: CRUD completo de sources, strategies, guides

**E2E Tests (Playwright):**
- [ ] Agregar fuente desde UI → aparece en tabla
- [ ] Evaluar fuente → score aparece
- [ ] Ver estrategias extraidas
- [ ] Generar guia → render markdown
- [ ] Chat: enviar pregunta → recibir respuesta con contexto

## 4. Gate de Salida (Fase 1 → Fase 2)

Todas estas condiciones deben cumplirse antes de iniciar Fase 2:

- [ ] 3 agentes funcionales (source, reader, synthesis)
- [ ] Pipeline end-to-end: URL → evaluacion → extraccion → guia maestra
- [ ] Al menos 5 papers procesados exitosamente
- [ ] Al menos 1 guia maestra generada con version 1
- [ ] RAG operativo: chat responde con contexto de papers procesados
- [ ] Dashboard con todas las paginas funcionales (overview, sources, strategies, guide, chat)
- [ ] Tests unitarios e integracion pasando
- [ ] Deploy en Vercel funcionando y accesible
- [ ] agent_logs registra todas las acciones con tokens y costos
- [ ] Background Functions ejecutan embedding/extraccion sin timeout

## 5. Definition of Done

Fase 1 esta completa cuando:

1. Un usuario puede agregar una URL, el sistema la evalua, extrae estrategias, y genera una guia maestra
2. El chat responde preguntas usando RAG con conocimiento de los papers procesados
3. Toda accion de agente queda logueada con tokens, costo y duracion
4. El dashboard muestra el estado completo del sistema
5. El pipeline puede re-ejecutarse para incorporar nuevos papers

## 6. P1 Pendientes (a resolver post-Fase 1)

Estos items quedan documentados pero NO bloquean el inicio de Fase 2:

1. **Map-reduce para Reader**: Reemplazar `slice(30000)` por procesamiento por secciones para papers largos
2. **Calibrar match_threshold**: Correr benchmark offline con precision@k y recall@k sobre preguntas control
3. **Control de contexto en Synthesis**: No serializar arrays completos de estrategias, usar top-N + resumen por lotes
4. **Re-analisis automatico**: Cron job o webhook para re-evaluar periodicamente (Vercel Cron)
