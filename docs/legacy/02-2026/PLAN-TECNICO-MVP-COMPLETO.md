# Plan Tecnico Completo: MVP Research Trading Agent

**Proyecto:** traiding-agentic
**Fecha:** 2026-02-15
**Version:** 1.0
**Autores:** Equipo de desarrollo

---

## Indice

1. [Vision y Objetivos](#1-vision-y-objetivos)
2. [Arquitectura General](#2-arquitectura-general)
3. [Stack Tecnologico](#3-stack-tecnologico)
4. [Modelo de Datos (Supabase)](#4-modelo-de-datos-supabase)
5. [Agente 1: Source Agent](#5-agente-1-source-agent)
6. [Agente 2: Reader Agent](#6-agente-2-reader-agent)
7. [Agente 3: Synthesis Agent](#7-agente-3-synthesis-agent)
8. [API Routes (Backend)](#8-api-routes-backend)
9. [Frontend (Dashboard + Chat)](#9-frontend-dashboard--chat)
10. [Integracion Vercel AI SDK](#10-integracion-vercel-ai-sdk)
11. [RAG con pgvector](#11-rag-con-pgvector)
12. [Fase 2: Trading Bot](#12-fase-2-trading-bot)
13. [Seguridad](#13-seguridad)
14. [Testing](#14-testing)
15. [Deploy y CI/CD](#15-deploy-y-cicd)
16. [Roadmap Detallado](#16-roadmap-detallado)
17. [Estructura de Archivos](#17-estructura-de-archivos)

---

## 1. Vision y Objetivos

### Vision
Construir un sistema de agentes de investigacion que recopile, analice y sintetice conocimiento de trading de multiples fuentes academicas y profesionales, generando una "guia maestra" de trading que luego alimente un bot de paper trading en Binance Testnet.

### Objetivos del MVP (Fase 1)
- Sistema de 3 agentes que evaluan, leen y sintetizan papers de trading
- Base de conocimiento vectorial para RAG (Retrieval Augmented Generation)
- Dashboard web para gestionar fuentes, ver estrategias y consultar la guia
- Chat conversacional con el agente que tiene contexto de toda la investigacion
- Re-analisis periodico para refinar estrategias

### Objetivos Fase 2
- Trading bot conectado a Binance Testnet (paper trading BTC)
- Risk manager determinista con limites fijos
- Dashboard con KPIs de performance de trading
- El bot usa la guia maestra como fuente de inteligencia

### Restricciones
- Capital simulado: 10,000 USDT en testnet
- Solo BTC/USDT como par de trading
- Sin dinero real en Fase 1 ni Fase 2 (solo paper trading)
- El LLM nunca controla parametros de riesgo (determinista)

---

## 2. Arquitectura General

### Diagrama de Flujo

```
                    +------------------+
                    |  Usuario (Web)   |
                    +--------+---------+
                             |
                    +--------v---------+
                    |  Next.js 16      |
                    |  (Vercel)        |
                    |  - Dashboard     |
                    |  - Chat UI       |
                    |  - API Routes    |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v---+  +------v------+  +----v--------+
     | Source      |  | Reader      |  | Synthesis   |
     | Agent       |  | Agent       |  | Agent       |
     | (Vercel AI) |  | (Vercel AI) |  | (Vercel AI) |
     +--------+----+  +------+------+  +------+------+
              |              |                 |
              +--------------+-----------------+
                             |
                    +--------v---------+
                    |    Gemini LLM    |
                    |  (Google AI)     |
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
     +--------v---------+        +---------v--------+
     |   Supabase        |        |   pgvector       |
     |   (PostgreSQL)    |        |   (embeddings)   |
     |   - sources       |        |   - paper_chunks |
     |   - extractions   |        |                  |
     |   - strategies    |        |                  |
     |   - guides        |        |                  |
     |   - logs          |        |                  |
     +-------------------+        +------------------+
```

### Principios de Arquitectura
1. **Serverless-first:** Todo corre en Vercel (funciones serverless + edge)
2. **Agentes desacoplados:** Cada agente es independiente, se comunican via DB
3. **LLM como cerebro, codigo como guardia:** El LLM decide estrategia, el codigo impone limites
4. **Event sourcing:** Toda accion se loguea para auditoria
5. **Versionado de guias:** Cada guia generada es inmutable, nueva version = nuevo registro

---

## 3. Stack Tecnologico

### Frontend
| Tecnologia | Version | Proposito |
|-----------|---------|-----------|
| Next.js | 16 | Framework React full-stack |
| React | 19 | UI library |
| TypeScript | 5.x | Type safety |
| Tailwind CSS | 4.x | Styling |
| SWR | 2.x | Data fetching + cache |

### Backend (Next.js API Routes)
| Tecnologia | Version | Proposito |
|-----------|---------|-----------|
| Vercel AI SDK | latest | Agentes + streaming |
| Supabase JS | latest | DB client |
| @ai-sdk/google | ^1.x | Provider Gemini para Vercel AI SDK |

### Infraestructura
| Servicio | Proposito | Tier |
|---------|-----------|------|
| Vercel | Hosting + serverless | Free/Pro |
| Supabase | PostgreSQL + pgvector + auth | Free |
| Google AI (Gemini) | LLM para agentes | Pay per use |

### Herramientas de Desarrollo
| Herramienta | Proposito |
|------------|-----------|
| Node.js | >= 20.9.0 (prerequisito, fijar en `engines` de package.json) |
| pnpm | Package manager |
| ESLint + Prettier | Linting + formatting |
| Vitest | Unit testing |
| Playwright | E2E testing |

---

## 4. Modelo de Datos (Supabase)

### Tabla: sources
Fuentes de informacion evaluadas por el Source Agent.

```sql
CREATE TABLE sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  url TEXT NOT NULL UNIQUE,
  title TEXT,
  authors TEXT,
  publication_year INTEGER,
  source_type TEXT CHECK (source_type IN ('paper', 'article', 'repo', 'book', 'video')) NOT NULL,

  -- Scores del Source Agent (1-10)
  relevance_score INTEGER CHECK (relevance_score BETWEEN 1 AND 10),
  credibility_score INTEGER CHECK (credibility_score BETWEEN 1 AND 10),
  applicability_score INTEGER CHECK (applicability_score BETWEEN 1 AND 10),
  overall_score INTEGER CHECK (overall_score BETWEEN 1 AND 10),

  -- Metadata
  tags TEXT[] DEFAULT '{}',
  summary TEXT,
  evaluation_reasoning TEXT, -- por que el agente dio ese score

  -- Status workflow
  status TEXT CHECK (status IN (
    'pending',      -- recien cargado, no evaluado
    'evaluating',   -- Source Agent esta evaluando
    'approved',     -- aprobado, listo para Reader
    'processing',   -- Reader Agent leyendo
    'processed',    -- Reader termino
    'rejected',     -- Source Agent lo rechazo
    'error'         -- error en procesamiento
  )) DEFAULT 'pending',
  rejection_reason TEXT,
  error_message TEXT,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  evaluated_at TIMESTAMPTZ,
  processed_at TIMESTAMPTZ
);

CREATE INDEX idx_sources_status ON sources(status);
CREATE INDEX idx_sources_overall_score ON sources(overall_score DESC);
CREATE INDEX idx_sources_tags ON sources USING GIN(tags);
```

### Tabla: paper_extractions
Informacion estructurada extraida de cada paper.

```sql
CREATE TABLE paper_extractions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,

  -- Contenido extraido
  strategies JSONB DEFAULT '[]', -- array de estrategias
  key_insights TEXT[] DEFAULT '{}',
  risk_warnings TEXT[] DEFAULT '{}',
  market_conditions TEXT[], -- en que condiciones aplica
  data_period TEXT, -- "2019-2023", "2015-2024"
  sample_size TEXT, -- "450 trades", "10,000 candles"

  -- Relaciones con otros papers
  contradicts JSONB DEFAULT '[]', -- [{source_id, topic, detail}]
  supports JSONB DEFAULT '[]', -- [{source_id, topic, detail}]

  -- Resumen
  raw_summary TEXT,
  executive_summary TEXT, -- resumen ejecutivo en 2-3 oraciones
  confidence_score INTEGER CHECK (confidence_score BETWEEN 1 AND 10),

  -- Metadata
  processing_model TEXT, -- que modelo de Gemini se uso
  processing_tokens INTEGER, -- tokens consumidos
  processed_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_extractions_source ON paper_extractions(source_id);
CREATE INDEX idx_extractions_confidence ON paper_extractions(confidence_score DESC);
```

### Tabla: strategies_found
Estrategias individuales encontradas en papers.

```sql
CREATE TABLE strategies_found (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  extraction_id UUID NOT NULL REFERENCES paper_extractions(id) ON DELETE CASCADE,

  -- Definicion de la estrategia
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  strategy_type TEXT CHECK (strategy_type IN (
    'momentum', 'mean_reversion', 'breakout', 'trend_following',
    'statistical_arbitrage', 'market_making', 'sentiment',
    'machine_learning', 'hybrid', 'other'
  )),

  -- Parametros
  market TEXT DEFAULT 'btc', -- 'btc', 'crypto', 'equities', 'general'
  timeframe TEXT, -- '1m', '5m', '15m', '1h', '4h', '1d', '1w'
  indicators TEXT[] DEFAULT '{}', -- ['RSI', 'SMA', 'MACD', etc.]
  entry_rules TEXT[] DEFAULT '{}',
  exit_rules TEXT[] DEFAULT '{}',
  position_sizing TEXT, -- descripcion de como dimensionar

  -- Resultados de backtest reportados en el paper
  backtest_results JSONB DEFAULT '{}',
  -- Ejemplo: {
  --   "sharpe_ratio": 1.8,
  --   "max_drawdown_pct": 12,
  --   "win_rate_pct": 62,
  --   "profit_factor": 1.6,
  --   "total_return_pct": 45,
  --   "period": "2019-2023",
  --   "sample_trades": 450,
  --   "market_tested": "BTCUSDT"
  -- }

  -- Limitaciones y riesgos
  limitations TEXT[] DEFAULT '{}',
  best_market_conditions TEXT[], -- 'trending', 'ranging', 'volatile', 'low_vol'
  worst_market_conditions TEXT[], -- condiciones donde falla

  -- Scoring
  confidence INTEGER CHECK (confidence BETWEEN 1 AND 10),
  evidence_strength TEXT CHECK (evidence_strength IN ('weak', 'moderate', 'strong')),

  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_strategies_type ON strategies_found(strategy_type);
CREATE INDEX idx_strategies_market ON strategies_found(market);
CREATE INDEX idx_strategies_confidence ON strategies_found(confidence DESC);
CREATE INDEX idx_strategies_indicators ON strategies_found USING GIN(indicators);
```

### Tabla: paper_chunks (pgvector)
Chunks de texto con embeddings para RAG.

```sql
-- Habilitar extension pgvector en Supabase
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE paper_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,

  -- Contenido
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  section_title TEXT, -- titulo de la seccion del paper
  page_number INTEGER,

  -- Embedding
  embedding VECTOR(1024), -- gemini-embedding-001 con outputDimensionality=1024

  -- Metadata para filtrado
  metadata JSONB DEFAULT '{}',
  -- Ejemplo: {
  --   "has_strategy": true,
  --   "has_backtest": true,
  --   "topics": ["momentum", "rsi"],
  --   "importance": "high"
  -- }

  created_at TIMESTAMPTZ DEFAULT now()
);

-- Indice para busqueda vectorial eficiente (HNSW recomendado para datasets < 100k)
CREATE INDEX idx_chunks_embedding ON paper_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_chunks_source ON paper_chunks(source_id);
CREATE INDEX idx_chunks_metadata ON paper_chunks USING GIN(metadata);
```

### Tabla: trading_guides
Guias maestras generadas por el Synthesis Agent.

```sql
CREATE TABLE trading_guides (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  version INTEGER NOT NULL UNIQUE,

  -- Metadata de generacion
  based_on_sources INTEGER NOT NULL, -- cuantas fuentes se usaron
  based_on_strategies INTEGER NOT NULL,
  sources_used UUID[] DEFAULT '{}', -- IDs de sources usadas

  -- Contenido de la guia
  primary_strategy JSONB NOT NULL, -- estrategia principal
  secondary_strategies JSONB DEFAULT '[]',
  market_conditions_map JSONB DEFAULT '{}',
  -- Ejemplo: {
  --   "trending_up": "momentum_long",
  --   "trending_down": "wait_or_short",
  --   "ranging": "mean_reversion",
  --   "high_volatility": "reduce_position",
  --   "low_volatility": "breakout_watch"
  -- }

  avoid_list TEXT[] DEFAULT '{}', -- cosas que NO hacer
  risk_parameters JSONB DEFAULT '{}', -- parametros de riesgo sugeridos

  -- Documentos generados
  full_guide_markdown TEXT NOT NULL, -- guia completa en markdown
  system_prompt TEXT NOT NULL, -- system prompt para el trading bot
  executive_summary TEXT, -- resumen en 3-5 oraciones

  -- Scoring
  confidence_score INTEGER CHECK (confidence_score BETWEEN 1 AND 10),
  limitations TEXT[] DEFAULT '{}',

  -- Diff con version anterior
  changes_from_previous TEXT, -- que cambio vs la version anterior

  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_guides_version ON trading_guides(version DESC);
```

### Tabla: agent_logs
Log de todas las acciones de los agentes.

```sql
CREATE TABLE agent_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name TEXT NOT NULL CHECK (agent_name IN ('source', 'reader', 'synthesis', 'trading', 'chat')),
  action TEXT NOT NULL, -- 'evaluate_source', 'extract_paper', 'generate_guide', etc.
  source_id UUID REFERENCES sources(id),

  -- Detalle
  input_summary TEXT, -- que recibio
  output_summary TEXT, -- que produjo
  reasoning TEXT, -- por que tomo esa decision
  tokens_input INTEGER, -- tokens de entrada
  tokens_output INTEGER, -- tokens de salida
  tokens_used INTEGER, -- total
  duration_ms INTEGER,
  model_used TEXT,
  estimated_cost_usd NUMERIC(10,6), -- costo estimado de la llamada

  -- Status
  status TEXT CHECK (status IN ('started', 'success', 'error', 'warning')),
  error_message TEXT,

  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_logs_agent ON agent_logs(agent_name);
CREATE INDEX idx_logs_created ON agent_logs(created_at DESC);
CREATE INDEX idx_logs_source ON agent_logs(source_id);
```

### Tabla: chat_messages
Historial de conversaciones.

```sql
CREATE TABLE chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  role TEXT CHECK (role IN ('user', 'assistant', 'system')) NOT NULL,
  content TEXT NOT NULL,
  metadata JSONB DEFAULT '{}', -- {sources_cited, strategies_mentioned, etc.}
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_chat_created ON chat_messages(created_at DESC);

-- RLS: habilitar desde MVP (previene exposicion accidental via Supabase client)
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategies_found ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE trading_guides ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- Politica permisiva para service_role (backend)
-- Crear politicas mas restrictivas al agregar auth de usuario
CREATE POLICY "service_role_full_access" ON sources FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON paper_extractions FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON strategies_found FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON paper_chunks FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON trading_guides FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON agent_logs FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON chat_messages FOR ALL USING (true);
```

---

## 5. Agente 1: Source Agent

### Responsabilidad
Evaluar la calidad y relevancia de fuentes de informacion de trading antes de invertir tiempo en procesarlas.

### System Prompt

```
Sos un evaluador experto de fuentes academicas y profesionales de trading.
Tu trabajo es determinar si una fuente (paper, articulo, repo) vale la pena
ser analizada en profundidad para extraer estrategias de trading de Bitcoin.

CRITERIOS DE EVALUACION (score 1-10 cada uno):

1. RELEVANCIA:
   - 9-10: Paper especificamente sobre trading de BTC/crypto con estrategias implementables
   - 7-8: Paper de trading general con conceptos aplicables a crypto
   - 5-6: Paper financiero con insights indirectamente utiles
   - 1-4: No relacionado o demasiado teorico sin aplicacion practica

2. CREDIBILIDAD:
   - 9-10: Publicado en journal peer-reviewed (Journal of Finance, etc.), muchas citas
   - 7-8: Preprint en arXiv/SSRN con buenos resultados, autor reconocido
   - 5-6: Blog tecnico de fuente reconocida (QuantConnect, etc.), con codigo
   - 3-4: Blog personal o articulo sin respaldo
   - 1-2: Fuente no verificable

3. APLICABILIDAD:
   - 9-10: Se puede implementar directamente con $10K, timeframe intraday/swing
   - 7-8: Requiere adaptacion menor para nuestro caso
   - 5-6: Conceptos utiles pero implementacion compleja
   - 3-4: Requiere infraestructura que no tenemos (HFT, colocacion)
   - 1-2: No implementable en nuestro contexto

OVERALL SCORE: Promedio ponderado (Relevancia 40%, Credibilidad 30%, Aplicabilidad 30%)

Si overall >= 6: APROBAR (status: approved)
Si overall < 6: RECHAZAR con razon clara (status: rejected)

RESPONDE SIEMPRE en formato JSON:
{
  "title": "titulo del paper",
  "authors": "autores",
  "publication_year": 2024,
  "relevance_score": 8,
  "credibility_score": 7,
  "applicability_score": 9,
  "overall_score": 8,
  "tags": ["momentum", "btc", "rsi"],
  "summary": "Resumen en 2-3 oraciones de que trata",
  "evaluation_reasoning": "Por que le di estos scores",
  "decision": "approved" | "rejected",
  "rejection_reason": null | "razon si es rechazado"
}
```

### Implementacion (Vercel AI SDK)

```typescript
// app/lib/agents/source-agent.ts
import { generateObject } from 'ai';
import { google } from '@ai-sdk/google';
import { z } from 'zod';
import { supabase } from '@/lib/supabase';

const sourceEvaluationSchema = z.object({
  title: z.string(),
  authors: z.string().optional(),
  publication_year: z.number().optional(),
  relevance_score: z.number().min(1).max(10),
  credibility_score: z.number().min(1).max(10),
  applicability_score: z.number().min(1).max(10),
  overall_score: z.number().min(1).max(10),
  tags: z.array(z.string()),
  summary: z.string(),
  evaluation_reasoning: z.string(),
  decision: z.enum(['approved', 'rejected']),
  rejection_reason: z.string().nullable(),
});

export async function evaluateSource(sourceId: string, url: string, rawContent: string) {
  // Log start
  await logAgentAction('source', 'evaluate_source', sourceId, 'started');

  const startTime = Date.now();

  const result = await generateObject({
    model: google('gemini-2.5-flash'),
    schema: sourceEvaluationSchema,
    system: SOURCE_AGENT_SYSTEM_PROMPT,
    prompt: `Evalua esta fuente:\nURL: ${url}\n\nContenido:\n${rawContent.slice(0, 15000)}`,
  });

  const evaluation = result.object;
  const duration = Date.now() - startTime;

  // Update source in DB
  await supabase.from('sources').update({
    title: evaluation.title,
    authors: evaluation.authors,
    publication_year: evaluation.publication_year,
    relevance_score: evaluation.relevance_score,
    credibility_score: evaluation.credibility_score,
    applicability_score: evaluation.applicability_score,
    overall_score: evaluation.overall_score,
    tags: evaluation.tags,
    summary: evaluation.summary,
    evaluation_reasoning: evaluation.evaluation_reasoning,
    status: evaluation.decision,
    rejection_reason: evaluation.rejection_reason,
    evaluated_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }).eq('id', sourceId);

  // Log completion
  await logAgentAction('source', 'evaluate_source', sourceId, 'success', {
    output_summary: `Score: ${evaluation.overall_score}/10, Decision: ${evaluation.decision}`,
    reasoning: evaluation.evaluation_reasoning,
    duration_ms: duration,
  });

  return evaluation;
}
```

### Flujo
1. Usuario agrega URL desde el dashboard
2. Se crea registro en `sources` con status `pending`
3. Se descarga el contenido de la URL (fetch HTML o descargar PDF)
4. Source Agent evalua con Gemini
5. Si score >= 6: status `approved`, listo para Reader
6. Si score < 6: status `rejected` con razon

---

## 6. Agente 2: Reader Agent

### Responsabilidad
Leer papers aprobados, extraer estrategias e insights estructurados, y crear embeddings para RAG.

### System Prompt

```
Sos un analista de investigacion de trading especializado en extraer
informacion accionable de papers academicos y articulos profesionales.

Tu objetivo es leer un paper de trading y extraer:

1. ESTRATEGIAS: Cada estrategia de trading mencionada, con todos los detalles
   necesarios para implementarla:
   - Nombre descriptivo
   - Tipo (momentum, mean_reversion, breakout, etc.)
   - Timeframe recomendado
   - Indicadores necesarios (con parametros exactos si se mencionan)
   - Reglas de entrada (lo mas especifico posible)
   - Reglas de salida (stop-loss, take-profit, trailing)
   - Sizing de posicion (si se menciona)
   - Resultados de backtest (Sharpe, drawdown, win rate, periodo)
   - Limitaciones y cuando NO funciona

2. INSIGHTS CLAVE: Ideas o descubrimientos importantes que no son estrategias
   en si pero informan decisiones de trading. Ejemplos:
   - "La volatilidad de BTC es 3x mayor los domingos"
   - "El volumen es mejor predictor que el precio en crypto"

3. ADVERTENCIAS DE RIESGO: Riesgos especificos mencionados en el paper.

4. RELACIONES: Si algo contradice o confirma hallazgos de otros papers
   que conozcas.

IMPORTANTE:
- Si el paper no tiene datos concretos de backtest, indicalo
- Si las reglas de entrada/salida son vagas, indicalo como limitacion
- Sigue el formato JSON exacto que se te pida
- No inventes datos que no estan en el paper
- Si un indicador se menciona sin parametros (ej: "RSI" sin periodo),
  usa el valor estandar (RSI 14) pero aclara que es default
```

### Implementacion

```typescript
// app/lib/agents/reader-agent.ts
import { generateObject, embed } from 'ai';
import { google } from '@ai-sdk/google';
import { z } from 'zod';

const extractionSchema = z.object({
  strategies: z.array(z.object({
    name: z.string(),
    description: z.string(),
    strategy_type: z.enum([
      'momentum', 'mean_reversion', 'breakout', 'trend_following',
      'statistical_arbitrage', 'market_making', 'sentiment',
      'machine_learning', 'hybrid', 'other'
    ]),
    market: z.string().default('btc'),
    timeframe: z.string().optional(),
    indicators: z.array(z.string()),
    entry_rules: z.array(z.string()),
    exit_rules: z.array(z.string()),
    position_sizing: z.string().optional(),
    backtest_results: z.object({
      sharpe_ratio: z.number().optional(),
      max_drawdown_pct: z.number().optional(),
      win_rate_pct: z.number().optional(),
      profit_factor: z.number().optional(),
      total_return_pct: z.number().optional(),
      period: z.string().optional(),
      sample_trades: z.number().optional(),
    }).optional(),
    limitations: z.array(z.string()),
    best_market_conditions: z.array(z.string()),
    worst_market_conditions: z.array(z.string()),
    confidence: z.number().min(1).max(10),
    evidence_strength: z.enum(['weak', 'moderate', 'strong']),
  })),
  key_insights: z.array(z.string()),
  risk_warnings: z.array(z.string()),
  executive_summary: z.string(),
  confidence_score: z.number().min(1).max(10),
});

export async function processSource(sourceId: string) {
  // 1. Get source content
  const { data: source } = await supabase
    .from('sources').select('*').eq('id', sourceId).single();

  // 2. Update status
  await supabase.from('sources')
    .update({ status: 'processing' }).eq('id', sourceId);

  // 3. Get full text (already fetched during evaluation, or re-fetch)
  const fullText = await fetchSourceContent(source.url);

  // 4. Chunk the text for embeddings
  const chunks = chunkText(fullText, 500); // ~500 tokens per chunk

  // 5. Generate embeddings and store in pgvector
  for (let i = 0; i < chunks.length; i++) {
    const { embedding } = await embed({
      model: google.embedding('gemini-embedding-001'),
      value: chunks[i].content,
      providerOptions: {
        google: { outputDimensionality: 1024 },
      },
    });

    await supabase.from('paper_chunks').insert({
      source_id: sourceId,
      chunk_index: i,
      content: chunks[i].content,
      section_title: chunks[i].section,
      embedding: embedding,
      metadata: { importance: chunks[i].importance },
    });
  }

  // 6. Extract structured information with Gemini
  // NOTA P1: Para papers largos (>30k chars), implementar map-reduce:
  //   - map: procesar por secciones/chunks independientes
  //   - reduce: fusionar hallazgos estructurados en un solo resultado
  // Por MVP, truncamos pero registramos si hubo perdida
  const truncated = fullText.length > 30000;
  const extraction = await generateObject({
    model: google('gemini-2.5-flash'),
    schema: extractionSchema,
    system: READER_AGENT_SYSTEM_PROMPT,
    prompt: `Analiza este paper de trading y extrae toda la informacion:\n\n${fullText.slice(0, 30000)}${truncated ? '\n\n[NOTA: contenido truncado, paper original mas largo]' : ''}`,
  });

  // 7. Save extraction and get the returned ID
  const { data: insertedExtraction } = await supabase
    .from('paper_extractions')
    .insert({
      source_id: sourceId,
      strategies: extraction.object.strategies,
      key_insights: extraction.object.key_insights,
      risk_warnings: extraction.object.risk_warnings,
      executive_summary: extraction.object.executive_summary,
      confidence_score: extraction.object.confidence_score,
    })
    .select('id')
    .single();

  const extractionId = insertedExtraction!.id;

  // 8. Save individual strategies
  for (const strategy of extraction.object.strategies) {
    await supabase.from('strategies_found').insert({
      source_id: sourceId,
      extraction_id: extractionId,
      ...strategy,
    });
  }

  // 9. Update source status
  await supabase.from('sources')
    .update({ status: 'processed', processed_at: new Date() })
    .eq('id', sourceId);

  return extraction.object;
}
```

### Chunking Strategy

```typescript
function chunkText(text: string, targetTokens: number = 500): Chunk[] {
  // 1. Split by sections (## headers)
  // 2. If section > targetTokens, split by paragraphs
  // 3. If paragraph > targetTokens, split by sentences
  // 4. Overlap: include last 50 tokens of previous chunk
  // 5. Tag each chunk with section title and estimated importance
}
```

---

## 7. Agente 3: Synthesis Agent

### Responsabilidad
Cruzar toda la informacion extraida, resolver contradicciones, y generar una guia de trading coherente y versionada.

### System Prompt

```
Sos un estratega de trading senior. Tu trabajo es sintetizar informacion
de multiples papers academicos y fuentes profesionales para generar
una guia de trading clara y accionable.

PROCESO:
1. Analiza todas las estrategias encontradas
2. Identifica patrones comunes (que dicen multiples fuentes)
3. Resuelve contradicciones dando mas peso a:
   - Papers con mejor backtest (mayor Sharpe, menor drawdown)
   - Papers mas recientes (datos post-2020)
   - Papers con mayor credibilidad (peer-reviewed > blog)
   - Papers con mayor muestra (mas trades = mas significativo)
4. Rankea estrategias por evidencia acumulada
5. Genera la guia con formato especifico

FORMATO DE LA GUIA:
- Estrategia principal (la mas respaldada)
- Estrategia(s) secundaria(s) (para condiciones de mercado alternativas)
- Mapa de condiciones: que estrategia usar en cada tipo de mercado
- Lista de "NO hacer" (con evidencia de por que)
- Parametros de riesgo sugeridos
- System prompt para el trading bot

RESTRICCIONES:
- Capital: ~$10,000 USDT
- Par: BTCUSDT
- Timeframe: intraday a swing (1h-1d)
- Max leverage: 2x
- El bot opera 24/7 pero no somos HFT
- Risk manager determinista (el LLM no controla riesgo)

IMPORTANTE:
- Se honesto sobre limitaciones
- Indica nivel de confianza para cada recomendacion
- Si hay poca evidencia, dilo claramente
- No inventes datos
```

### Implementacion

```typescript
// app/lib/agents/synthesis-agent.ts
export async function generateTradingGuide() {
  // 1. Fetch all processed extractions and strategies
  const { data: strategies } = await supabase
    .from('strategies_found')
    .select('*, sources(*)')
    .order('confidence', { ascending: false });

  const { data: extractions } = await supabase
    .from('paper_extractions')
    .select('*, sources(*)')
    .order('confidence_score', { ascending: false });

  // 2. Get current guide version
  const { data: lastGuide } = await supabase
    .from('trading_guides')
    .select('version')
    .order('version', { ascending: false })
    .limit(1)
    .single();

  const newVersion = (lastGuide?.version || 0) + 1;

  // 3. Generate guide with Gemini
  const guide = await generateObject({
    model: google('gemini-2.5-flash'),
    schema: tradingGuideSchema,
    system: SYNTHESIS_AGENT_SYSTEM_PROMPT,
    prompt: `
      Genera la Trading Guide v${newVersion}.

      ESTRATEGIAS ENCONTRADAS (${strategies.length}):
      ${JSON.stringify(strategies, null, 2)}

      EXTRACCIONES DE PAPERS (${extractions.length}):
      ${JSON.stringify(extractions, null, 2)}

      ${lastGuide ? `GUIA ANTERIOR (v${lastGuide.version}):\n${lastGuide.full_guide_markdown}` : 'Esta es la primera guia.'}
    `,
  });

  // 4. Save guide
  await supabase.from('trading_guides').insert({
    version: newVersion,
    based_on_sources: new Set(strategies.map(s => s.source_id)).size,
    based_on_strategies: strategies.length,
    ...guide.object,
  });

  return guide.object;
}
```

---

## 8. API Routes (Backend)

Todas las rutas son Next.js API Routes (App Router):

### Sources

```
POST   /api/sources              - Agregar nueva fuente (body: {url})
GET    /api/sources              - Listar fuentes (?status=approved&sort=score)
GET    /api/sources/[id]         - Detalle de una fuente
POST   /api/sources/[id]/evaluate - Trigger Source Agent
POST   /api/sources/[id]/process  - Trigger Reader Agent
DELETE /api/sources/[id]         - Eliminar fuente
```

### Strategies

```
GET    /api/strategies           - Listar estrategias (?type=momentum&market=btc)
GET    /api/strategies/[id]      - Detalle de una estrategia
GET    /api/strategies/stats     - Estadisticas (total, por tipo, avg confidence)
```

### Guides

```
POST   /api/guides/generate      - Trigger Synthesis Agent
GET    /api/guides/current        - Guia actual (latest version)
GET    /api/guides/[version]      - Guia por version
GET    /api/guides/history        - Listado de todas las versiones
GET    /api/guides/system-prompt  - Solo el system prompt generado
```

### Chat

```
POST   /api/chat                 - Enviar mensaje (streaming response)
GET    /api/chat/history         - Historial de mensajes
```

### Pipeline

```
POST   /api/pipeline/run         - Ejecutar pipeline completo (evaluate -> process -> synthesize)
GET    /api/pipeline/status      - Estado del pipeline
```

### Stats

```
GET    /api/stats                - KPIs generales del sistema
```

---

## 9. Frontend (Dashboard + Chat)

### Estructura de Paginas

```
app/
  page.tsx                    -- Overview / Dashboard principal
  sources/
    page.tsx                  -- Lista de fuentes
    [id]/page.tsx            -- Detalle de fuente
    new/page.tsx             -- Agregar nueva fuente
  strategies/
    page.tsx                  -- Lista de estrategias
    [id]/page.tsx            -- Detalle de estrategia
  guide/
    page.tsx                  -- Guia maestra actual
    history/page.tsx         -- Historial de guias
  chat/
    page.tsx                  -- Chat con el agente
  settings/
    page.tsx                  -- Configuracion
```

### Overview Page (Dashboard Principal)
Cards con:
- Total fuentes: 12 (8 aprobadas, 3 rechazadas, 1 pendiente)
- Total estrategias: 24 encontradas
- Guia version: v3 (confianza 7/10)
- Ultimo update: hace 2 horas

Tabla reciente:
- Ultimas 5 acciones de los agentes (log)

### Sources Page
Tabla con columnas: Titulo | Tipo | Score | Tags | Status | Acciones
- Filtros por status, tipo, score
- Boton "Agregar URL" abre modal
- Acciones: Evaluar, Procesar, Ver detalle, Eliminar

### Strategies Page
Tabla: Nombre | Tipo | Timeframe | Indicadores | Confianza | Paper origen
- Filtros por tipo, mercado, confianza
- Click para ver detalle completo con entry/exit rules

### Guide Page
- Render del markdown de la guia actual
- Sidebar con metadata (version, fuentes usadas, confianza)
- Boton "Re-generar guia"
- Tabs para ver "Full Guide" | "System Prompt" | "Historial"

### Chat Page
- Interfaz de chat tipo ChatGPT
- El agente tiene acceso a toda la DB via RAG
- Streaming de respuestas con Vercel AI SDK `useChat()`

---

## 10. Integracion Vercel AI SDK

### Setup

```typescript
// app/lib/ai.ts
import { createGoogleGenerativeAI } from '@ai-sdk/google';

export const google = createGoogleGenerativeAI({
  apiKey: process.env.GOOGLE_AI_API_KEY,
});

export const gemini = google('gemini-2.5-flash');
```

### Chat con RAG

```typescript
// app/api/chat/route.ts
import { streamText } from 'ai';
import { google } from '@/lib/ai';

export async function POST(req: Request) {
  const { messages } = await req.json();
  const lastMessage = messages[messages.length - 1].content;

  // 1. Generate embedding of the question
  const { embedding } = await embed({
    model: google.embedding('gemini-embedding-001'),
    value: lastMessage,
    providerOptions: {
      google: { outputDimensionality: 1024 },
    },
  });

  // 2. Search similar chunks in pgvector
  const { data: relevantChunks } = await supabase.rpc('match_chunks', {
    query_embedding: embedding,
    match_threshold: 0.7,
    match_count: 5,
  });

  // 3. Get current trading guide
  const { data: guide } = await supabase
    .from('trading_guides')
    .select('full_guide_markdown')
    .order('version', { ascending: false })
    .limit(1)
    .single();

  // 4. Build context
  const context = `
    GUIA DE TRADING ACTUAL:
    ${guide?.full_guide_markdown || 'No hay guia generada aun.'}

    FRAGMENTOS RELEVANTES DE PAPERS:
    ${relevantChunks?.map(c => c.content).join('\n---\n') || 'No hay papers procesados aun.'}
  `;

  // 5. Stream response
  const result = streamText({
    model: google('gemini-2.5-flash'),
    system: `Sos un asistente experto en trading que responde preguntas
             basandose en papers academicos y la guia de trading generada.
             Siempre cita las fuentes cuando sea posible.\n\n${context}`,
    messages,
  });

  return result.toDataStreamResponse();
}
```

### Supabase RPC para Vector Search

```sql
CREATE OR REPLACE FUNCTION match_chunks(
  query_embedding VECTOR(1024),
  match_threshold FLOAT DEFAULT 0.7,
  match_count INT DEFAULT 5
)
RETURNS TABLE (
  id UUID,
  source_id UUID,
  content TEXT,
  section_title TEXT,
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    pc.id,
    pc.source_id,
    pc.content,
    pc.section_title,
    1 - (pc.embedding <=> query_embedding) AS similarity
  FROM paper_chunks pc
  WHERE 1 - (pc.embedding <=> query_embedding) > match_threshold
  ORDER BY pc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
```

---

## 11. RAG con pgvector

### Flujo de RAG

```
Pregunta del usuario
       |
       v
Generar embedding de la pregunta (Gemini gemini-embedding-001)
       |
       v
Buscar chunks similares en pgvector (cosine similarity > 0.7)
       |
       v
Tomar top 5 chunks mas relevantes
       |
       v
Agregar como contexto al prompt de Gemini
       |
       v
Gemini responde con conocimiento de los papers
```

### Embedding Model
- **Modelo:** `gemini-embedding-001` de Google (1024 dimensiones via outputDimensionality, default 3072)
- **Costo:** Consultar pricing oficial vigente en https://ai.google.dev/gemini-api/docs/pricing (precios cambian frecuentemente)
- **Alternativa:** `gemini-embedding-001` (modelo mas nuevo de Google) u OpenAI `text-embedding-3-small` (1536 dims)

### Chunk Size Optimization
- Target: 500 tokens por chunk (~375 palabras)
- Overlap: 50 tokens con el chunk anterior
- Metadata: seccion, pagina, importancia estimada
- Pre-filtrado: se pueden filtrar chunks por metadata antes de la busqueda vectorial

---

## 12. Fase 2: Trading Bot

### Entornos Binance (Separacion estricta)

| Scope | REST base | WebSocket base |
|---|---|---|
| Spot Testnet | `https://testnet.binance.vision` | `wss://stream.testnet.binance.vision/ws` |
| Futures Demo (USDT-M) | `https://demo-fapi.binance.com` | `wss://fstream.binancefuture.com` |

> **Importante:** El `execution-adapter` debe validar `BINANCE_ENV` en runtime. Si `BINANCE_ENV != spot_testnet` o `demo_futures`, rechazar toda orden. Loguear base URL efectiva en cada operacion.

### Market Data (Binance Testnet WebSocket)

```typescript
// Conexion WebSocket a Binance Testnet
const ws = new WebSocket('wss://stream.testnet.binance.vision/ws/btcusdt@kline_1m');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  const kline = {
    timestamp: data.k.t,
    open: parseFloat(data.k.o),
    high: parseFloat(data.k.h),
    low: parseFloat(data.k.l),
    close: parseFloat(data.k.c),
    volume: parseFloat(data.k.v),
    isClosed: data.k.x, // true when candle closes
  };

  if (kline.isClosed) {
    candleBuffer.push(kline);
    recalculateIndicators();
  }
};
```

### Indicators Engine

```typescript
// Calculados sobre el buffer de las ultimas 200 velas
interface Indicators {
  sma_10: number;      // Simple Moving Average 10 periodos
  sma_50: number;      // Simple Moving Average 50 periodos
  rsi_14: number;      // Relative Strength Index 14 periodos
  bb_upper: number;    // Bollinger Band superior (SMA_20 + 2*stddev)
  bb_lower: number;    // Bollinger Band inferior (SMA_20 - 2*stddev)
  bb_middle: number;   // Bollinger Band medio (SMA_20)
  volume_avg_20: number; // Volumen promedio 20 periodos
  volume_ratio: number;  // Volumen actual / promedio
  atr_14: number;      // Average True Range (volatilidad)
}
```

### Strategy Advisor (Gemini con Guia Maestra)

Cada 5 minutos:
1. Recopilar indicadores actuales
2. Cargar la guia maestra (system prompt generado)
3. Preguntar a Gemini que estrategia aplicar
4. Ejecutar la estrategia elegida de forma determinista

### Risk Manager (Determinista)

```typescript
interface RiskLimits {
  maxDailyLossPct: 2;        // -2% max loss per day
  maxPositionSizeBTC: 0.001; // ~$100 per trade
  maxOpenPositions: 1;        // 1 position at a time
  stopLossPct: 1.5;          // -1.5% auto stop-loss
  takeProfitPct: 3;          // +3% auto take-profit
  maxLeverage: 1;            // No leverage for MVP
  cooldownAfterLossMinutes: 30; // Wait 30min after a loss
}
```

### 12.6 Trade Proposal Workflow (HITL Hibrido)

Toda decision del LLM genera un `TradeProposal`, nunca una orden directa al exchange.

**Flujo completo:**
```
LLM decide estrategia
    → Crear TradeProposal (status: draft)
    → Risk Manager valida limites
        → Si rechazado: status: risk_rejected, loguear razon, fin
        → Si valido: status: validated
    → Evaluar threshold HITL:
        - notional < AUTO_APPROVE_THRESHOLD_USDT ($100):
            → status: auto_approved → ejecutar
        - notional >= threshold:
            → status: pending_approval
            → Enviar push notification al operador
            → Timer SLA: 5 minutos
    → Operador en dashboard /approvals:
        - Aprobar: status: approved → ejecutar
        - Rechazar: status: rejected → loguear razon, fin
        - No responde: status: expired → cancelar, loguear
    → Ejecucion:
        → Generar client_order_id unico (UUID)
        → Enviar al BrokerAdapter activo (simulador o exchange)
        → status: executed | failed
        → Loguear resultado completo con correlation_id
```

**Maquina de estados de TradeProposal:**
```
draft → validated → auto_approved → executed | failed
                  → pending_approval → approved → executed | failed
                                     → rejected
                                     → expired
                  → risk_rejected
                  → cancelled (manual)
```

**Configuracion via env:**
```
AUTO_APPROVE_THRESHOLD_USDT=100   # Ordenes < $100 se auto-aprueban
HITL_SLA_SECONDS=300              # 5 min para aprobar antes de expirar
HITL_NOTIFICATIONS=push,email     # Canales de notificacion
```

### 12.7 Simulated Broker Adapter

El bot NO toca Binance al principio. Opera contra un simulador local determinista.

**Interface comun (todos los adapters implementan esto):**

```typescript
interface BrokerAdapter {
  placeOrder(proposal: ValidatedProposal): Promise<OrderResult>;
  cancelOrder(orderId: string): Promise<CancelResult>;
  getOpenOrders(): Promise<Order[]>;
  getPositions(): Promise<Position[]>;
  getBalance(): Promise<Balance>;
  getOrderStatus(orderId: string): Promise<OrderStatus>;
}

// Implementaciones:
class SimulatedBroker implements BrokerAdapter {
  // Balance virtual, posiciones en memoria/DB
  // Slippage configurable (default 5 bps)
  // Latencia simulada (default 100ms)
  // Soporta replay de datos historicos para backtesting
}

class BinanceSpotTestnet implements BrokerAdapter {
  // REST: https://testnet.binance.vision
  // WS: wss://stream.testnet.binance.vision/ws
}

class BinanceFuturesDemo implements BrokerAdapter {
  // REST: https://demo-fapi.binance.com
  // WS: wss://fstream.binancefuture.com
}
```

**Seleccion via env:** `BROKER_ADAPTER=simulated|spot_testnet|demo_futures`

**Simulador con replay de datos historicos:**

```typescript
interface SimulatorConfig {
  initialBalanceUsdt: number;     // default 10000
  slippageBps: number;            // default 5 (0.05%)
  simulatedLatencyMs: number;     // default 100
  replayMode: boolean;            // si true, alimenta con klines historicas
  replayDataPath?: string;        // path a CSV/JSON de klines historicas
  replaySpeedMultiplier?: number; // 1x = tiempo real, 10x = 10 veces mas rapido
}
```

**Criterio de graduacion a Binance Testnet:**
1. Minimo 7 dias operando estable en simulador
2. Sin circuit breakers activados en nivel critico
3. Sharpe ratio > 0 (no pierde consistentemente)
4. Error rate < 1%
5. Reconciliacion sin divergencias por 48h

### 12.8 Circuit Breakers Avanzados

Extienden el Risk Manager con proteccion automatica en 3 niveles:

```typescript
interface CircuitBreakers {
  // === Trading Breakers ===
  maxConsecutiveLosses: 3;          // 3 perdidas seguidas → bloqueo
  maxDailyLossPct: 2;              // -2% diario (ya existe en Risk Manager)

  // === Infrastructure Breakers ===
  maxSlippageBps: 20;              // slippage real > 20 bps → alerta + review
  latencyGuardMs: 5000;            // exchange tarda > 5s → pausar trading
  maxOrderRejectionsPerHour: 5;    // 5 rechazos/hora → bloquear + investigar

  // === LLM Breakers ===
  maxLlmErrorsPerHour: 10;        // Gemini falla 10 veces → fallback/pausa
  maxDailyLlmCostUsd: 5;          // Costo LLM > $5/dia → pausar agentes
}
```

**Acciones por tipo de breaker:**

| Breaker | Accion primaria | Accion secundaria |
|---|---|---|
| `maxConsecutiveLosses` | Bloquear nuevas ordenes | Alerta push al operador |
| `maxDailyLossPct` | Bloquear ordenes + cerrar posiciones | Alerta + loguear PnL final |
| `maxSlippageBps` | Alerta + pausar 15 min | Review manual requerido |
| `latencyGuardMs` | Pausar trading | Alerta + check de salud del exchange |
| `maxOrderRejectionsPerHour` | Bloquear ordenes | Investigar causa (rate limit? fondos?) |
| `maxLlmErrorsPerHour` | Pausar agentes LLM | Fallback a ultima decision valida |
| `maxDailyLlmCostUsd` | Pausar agentes LLM | Alerta de presupuesto |

**Cada activacion se registra en `risk_breaker_events` con:**
- breaker_name, trigger_value, threshold_value
- action_taken, duration_seconds
- resolved_at (cuando se desactiva)

### 12.9 Reconciliacion e Idempotencia

**Idempotencia:**
- Cada `TradeProposal` genera un `client_order_id` unico (UUID v4)
- Se envia al exchange como `newClientOrderId`
- Si se reenvia la misma propuesta, el exchange ignora el duplicado
- Constraint `UNIQUE(client_order_id)` en tabla `execution_orders`

**Reconciliacion periodica (cada 60 segundos):**

```typescript
async function reconcile(): Promise<ReconciliationResult> {
  // 1. Consultar estado real del exchange
  const exchangeOrders = await broker.getOpenOrders();
  const exchangePositions = await broker.getPositions();
  const exchangeBalance = await broker.getBalance();

  // 2. Consultar estado en DB
  const dbOrders = await getActiveOrdersFromDB();
  const dbPositions = await getOpenPositionsFromDB();

  // 3. Detectar divergencias
  const divergences: Divergence[] = [];

  // Ordenes en exchange que no estan en DB
  for (const order of exchangeOrders) {
    if (!dbOrders.find(o => o.client_order_id === order.clientOrderId)) {
      divergences.push({ type: 'orphan_exchange_order', order });
    }
  }

  // Ordenes en DB marcadas como 'executed' pero no en exchange
  for (const order of dbOrders) {
    if (!exchangeOrders.find(o => o.clientOrderId === order.client_order_id)) {
      divergences.push({ type: 'missing_exchange_order', order });
    }
  }

  // 4. Reparar y alertar
  for (const d of divergences) {
    await repairDivergence(d);
    await alertOperator(d);
  }

  // 5. Loguear resultado
  return {
    timestamp: new Date(),
    orders_synced: exchangeOrders.length,
    positions_synced: exchangePositions.length,
    divergences_found: divergences,
    balance_exchange: exchangeBalance,
  };
}
```

**Dead-letter para ordenes fallidas:**
- Si una orden falla 3 veces → mover a `dead_letter` status
- Requiere intervencion manual del operador
- Alerta push inmediata

### 12.10 Logs Inmutables y Observabilidad Operativa

**Extension de agent_logs para trazabilidad:**
- `correlation_id` (UUID) → traza end-to-end: proposal → order → fill → reconciliation
- `actor` (`agent|human|system|breaker`) → quien inicio la accion
- Politica RLS: bloquear DELETE en todas las tablas de logs (inmutabilidad)

**Metricas operativas (pagina /operations):**

| Metrica | Descripcion | Calculo |
|---|---|---|
| `proposal_to_approval_ms` | Tiempo hasta aprobacion humana | approved_at - created_at |
| `approval_to_execution_ms` | Tiempo hasta ejecucion | executed_at - approved_at |
| `fill_rate` | % propuestas ejecutadas exitosamente | executed / total proposals |
| `rejection_rate` | % rechazadas por humano o riesgo | (rejected + risk_rejected) / total |
| `slippage_bps_realized` | Slippage real vs precio propuesto | (fill_price - proposal_price) / proposal_price * 10000 |
| `breaker_trigger_count` | Activaciones de circuit breakers | COUNT(risk_breaker_events) per day |
| `llm_tokens_cost_daily` | Costo diario LLM por agente | SUM(estimated_cost_usd) per agent per day |
| `reconciliation_divergences` | Divergencias encontradas | COUNT(divergences) per reconciliation run |
| `sharpe_ratio_rolling` | Sharpe ratio ultimos 30 dias | (avg_return - risk_free) / std_return |
| `win_rate` | % de trades ganadores | winning_trades / total_closed_trades |

### 12.11 Modelo de Datos Fase 2 (SQL)

```sql
-- Trade Proposals (toda decision del LLM pasa por aca)
CREATE TABLE trade_proposals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  correlation_id UUID NOT NULL DEFAULT gen_random_uuid(),

  -- Propuesta
  symbol TEXT NOT NULL DEFAULT 'BTCUSDT',
  side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
  order_type TEXT NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT')),
  quantity NUMERIC(18,8) NOT NULL,
  price NUMERIC(18,2), -- null para MARKET
  notional_usdt NUMERIC(18,2) NOT NULL, -- valor total en USDT
  strategy_name TEXT NOT NULL, -- 'momentum_long', 'mean_reversion', etc.
  reasoning TEXT, -- explicacion del LLM

  -- HITL
  status TEXT NOT NULL CHECK (status IN (
    'draft', 'validated', 'risk_rejected',
    'auto_approved', 'pending_approval',
    'approved', 'rejected', 'expired',
    'executed', 'failed', 'cancelled'
  )) DEFAULT 'draft',
  approved_by TEXT, -- 'auto' | user_id
  approval_reason TEXT,
  rejection_reason TEXT,

  -- Risk check
  risk_check_passed BOOLEAN,
  risk_check_details JSONB DEFAULT '{}',

  -- Timing
  created_at TIMESTAMPTZ DEFAULT now(),
  validated_at TIMESTAMPTZ,
  approved_at TIMESTAMPTZ,
  executed_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ, -- created_at + HITL_SLA_SECONDS

  -- Metadata
  indicators_snapshot JSONB DEFAULT '{}', -- indicadores al momento de la propuesta
  guide_version INTEGER -- version de la guia maestra usada
);

CREATE INDEX idx_proposals_status ON trade_proposals(status);
CREATE INDEX idx_proposals_correlation ON trade_proposals(correlation_id);
CREATE INDEX idx_proposals_created ON trade_proposals(created_at DESC);
ALTER TABLE trade_proposals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_full_access" ON trade_proposals FOR ALL USING (true);

-- Execution Orders (ordenes enviadas al exchange/simulador)
CREATE TABLE execution_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  proposal_id UUID NOT NULL REFERENCES trade_proposals(id),
  correlation_id UUID NOT NULL,

  -- Identificacion
  client_order_id UUID NOT NULL UNIQUE, -- idempotencia
  exchange_order_id TEXT, -- ID devuelto por el exchange

  -- Detalles
  broker_adapter TEXT NOT NULL, -- 'simulated' | 'spot_testnet' | 'demo_futures'
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  order_type TEXT NOT NULL,
  quantity NUMERIC(18,8) NOT NULL,
  requested_price NUMERIC(18,2),

  -- Fill
  fill_price NUMERIC(18,2),
  fill_quantity NUMERIC(18,8),
  slippage_bps NUMERIC(10,2), -- slippage real en basis points
  commission NUMERIC(18,8),

  -- Status
  status TEXT NOT NULL CHECK (status IN (
    'pending', 'submitted', 'partially_filled',
    'filled', 'cancelled', 'rejected', 'expired',
    'failed', 'dead_letter'
  )) DEFAULT 'pending',
  error_message TEXT,
  retry_count INTEGER DEFAULT 0,

  -- Timing
  created_at TIMESTAMPTZ DEFAULT now(),
  submitted_at TIMESTAMPTZ,
  filled_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_orders_proposal ON execution_orders(proposal_id);
CREATE INDEX idx_orders_correlation ON execution_orders(correlation_id);
CREATE INDEX idx_orders_client ON execution_orders(client_order_id);
CREATE INDEX idx_orders_status ON execution_orders(status);
ALTER TABLE execution_orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_full_access" ON execution_orders FOR ALL USING (true);

-- Reconciliation Runs
CREATE TABLE reconciliation_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  broker_adapter TEXT NOT NULL,

  -- Resultado
  orders_synced INTEGER NOT NULL DEFAULT 0,
  positions_synced INTEGER NOT NULL DEFAULT 0,
  divergences_found INTEGER NOT NULL DEFAULT 0,
  divergence_details JSONB DEFAULT '[]',
  actions_taken JSONB DEFAULT '[]',

  -- Balance snapshot
  balance_snapshot JSONB DEFAULT '{}',

  -- Status
  status TEXT CHECK (status IN ('running', 'success', 'error')) DEFAULT 'running',
  error_message TEXT,
  duration_ms INTEGER,

  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_recon_created ON reconciliation_runs(created_at DESC);
ALTER TABLE reconciliation_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_full_access" ON reconciliation_runs FOR ALL USING (true);

-- Risk Breaker Events
CREATE TABLE risk_breaker_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Breaker info
  breaker_name TEXT NOT NULL, -- 'maxConsecutiveLosses', 'latencyGuardMs', etc.
  breaker_category TEXT NOT NULL CHECK (breaker_category IN ('trading', 'infrastructure', 'llm')),
  trigger_value NUMERIC(18,4) NOT NULL, -- valor que disparo el breaker
  threshold_value NUMERIC(18,4) NOT NULL, -- umbral configurado

  -- Accion
  action_taken TEXT NOT NULL, -- 'block_new_orders', 'pause_agents', etc.
  notification_sent BOOLEAN DEFAULT false,

  -- Resolucion
  resolved_at TIMESTAMPTZ, -- null si sigue activo
  resolved_by TEXT, -- 'auto' | 'manual' | user_id
  resolution_notes TEXT,

  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_breakers_name ON risk_breaker_events(breaker_name);
CREATE INDEX idx_breakers_created ON risk_breaker_events(created_at DESC);
CREATE INDEX idx_breakers_active ON risk_breaker_events(resolved_at) WHERE resolved_at IS NULL;
ALTER TABLE risk_breaker_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_full_access" ON risk_breaker_events FOR ALL USING (true);
```

### 12.12 API Routes Fase 2

```
# Trade Proposals (HITL)
POST   /api/proposals              - Crear propuesta (uso interno del agente)
GET    /api/proposals              - Listar propuestas (?status=pending_approval)
GET    /api/proposals/[id]         - Detalle de propuesta con ordenes
POST   /api/proposals/[id]/approve - Aprobar propuesta (humano)
POST   /api/proposals/[id]/reject  - Rechazar propuesta (humano, body: {reason})

# Execution
GET    /api/orders                 - Listar ordenes (?status=filled&adapter=simulated)
GET    /api/orders/[id]            - Detalle de orden con fill info

# Reconciliation
POST   /api/reconciliation/run     - Trigger reconciliacion manual
GET    /api/reconciliation/history - Historial de reconciliaciones
GET    /api/reconciliation/latest  - Ultima reconciliacion

# Risk & Breakers
GET    /api/risk/breakers          - Estado actual de todos los breakers
GET    /api/risk/breakers/history  - Historial de activaciones
POST   /api/risk/breakers/[name]/resolve - Resolver breaker manualmente

# Operations & Metrics
GET    /api/operations/metrics     - Metricas operativas (KPIs)
GET    /api/operations/pnl         - PnL diario/acumulado
GET    /api/operations/health      - Health check del sistema completo

# Simulator
POST   /api/simulator/config       - Configurar simulador (slippage, latency, etc.)
POST   /api/simulator/replay       - Iniciar replay de datos historicos
GET    /api/simulator/status        - Estado del simulador
```

### 12.13 Frontend Pages Fase 2

```
/approvals        - Cola HITL: propuestas pendientes con boton aprobar/rechazar
                    Timer visual de SLA, detalles de indicadores, razon del LLM
/trading          - Dashboard de trading en vivo:
                    Precio BTC, posicion abierta, PnL, ultimo trade
/operations       - Centro de operaciones:
                    Estado de breakers (verde/rojo), metricas, reconciliacion
                    Log de eventos con filtro por correlation_id
/history          - Historial completo de proposals + orders + fills
                    Exportar a CSV
/simulator        - Configuracion del simulador, replay de historicos,
                    resultados de backtesting, comparacion sim vs real
```

### 12.14 Dashboard Trading KPIs

- Precio BTC en vivo
- Ganancia del dia ($$$ y %)
- Ganancia acumulada total ($$$ y %)
- Total operaciones realizadas
- Operaciones ganadoras vs perdedoras (count + %)
- Ganancia promedio vs perdida promedio
- Ratio ganancia/perdida (win rate)
- Sharpe ratio rolling 30 dias
- Posicion abierta actual con P&L en tiempo real
- Stop-loss y take-profit actuales
- Log de decisiones del agente
- Estado de circuit breakers (indicador verde/amarillo/rojo)
- Proxima reconciliacion (countdown)
- Costo LLM del dia

### 12.15 Roadmap Fase 2

> **Nota:** Fase 2 inicia despues de completar Fase 1 (Research Agent, Semanas 1-4).

#### Semana 5-6: Trading Core
- [ ] Implementar `SimulatedBroker` con slippage y latencia configurable
- [ ] Implementar `BrokerAdapter` interface
- [ ] Implementar `TradeProposal` workflow completo (maquina de estados)
- [ ] Implementar Risk Manager extendido con circuit breakers
- [ ] API routes: proposals CRUD + approve/reject
- [ ] Pagina /approvals con timer SLA y push notifications
- [ ] Conectar Strategy Advisor (Gemini + Guia Maestra) → proposals
- [ ] Tests: transicion de estados HITL, idempotencia, breakers

#### Semana 7-8: Ejecucion + Reconciliacion
- [ ] Implementar idempotencia con `client_order_id`
- [ ] Implementar reconciliacion periodica (cada 60s)
- [ ] Implementar dead-letter para ordenes fallidas
- [ ] Implementar `BinanceSpotTestnet` adapter
- [ ] Implementar `BinanceFuturesDemo` adapter
- [ ] API routes: orders, reconciliation, risk breakers
- [ ] Pagina /operations con metricas y estado breakers
- [ ] Tests: reconciliacion con estado divergente, retry/backoff

#### Semana 9-10: Observabilidad + Simulador Avanzado
- [ ] Implementar replay de datos historicos en SimulatedBroker
- [ ] Pagina /simulator con config y resultados de backtesting
- [ ] Metricas operativas completas (Sharpe, fill rate, slippage, costs)
- [ ] Pagina /history con exportacion CSV
- [ ] Push notifications (email + browser push) para HITL y breakers
- [ ] Criterio de graduacion automatico (sim → testnet)

#### Semana 11-12: Hardening + Piloto
- [ ] 7 dias de simulador estable (criterio de graduacion)
- [ ] Migrar a Binance Testnet con volumenes minimos
- [ ] Monitoreo continuo de breakers en produccion demo
- [ ] Documentacion: playbooks de fallo, runbooks operativos
- [ ] Review final de seguridad y permisos

### 12.16 Definition of Done (Fase 2)

Fase 2 se considera completa cuando:

- [ ] No hay ejecucion de orden sin pasar por TradeProposal workflow
- [ ] HITL funcional: ordenes > $100 requieren aprobacion humana
- [ ] Push notifications operativas para aprobaciones y breakers
- [ ] Simulador estable por minimo 7 dias
- [ ] Reconciliacion automatica activa sin divergencias por 48h
- [ ] Idempotencia validada por tests (doble submit no genera duplicados)
- [ ] Circuit breakers operativos en 3 niveles (trading, infra, LLM)
- [ ] Trazabilidad completa por `correlation_id` (proposal → order → fill)
- [ ] Metricas operativas visibles en /operations
- [ ] Sharpe ratio > 0 en simulador (no pierde consistentemente)
- [ ] Error rate < 1% sostenido por 7 dias

---

## 13. Seguridad

### Principios
1. **API keys nunca en el frontend** — solo en env vars del servidor
2. **El LLM nunca controla parametros de riesgo** — son deterministas
3. **Validacion de input y proteccion SSRF** — URLs sanitizadas, rate limiting, allowlist/denylist de dominios, bloqueo de IPs privadas/metadata endpoints, timeout + max bytes + content-type whitelist en el fetcher
4. **Row Level Security en Supabase** — habilitar desde MVP (aunque sea single-tenant, previene exposicion accidental)
5. **Logs de todo** — cada accion del agente queda registrada

### Env Variables

```
# Supabase
NEXT_PUBLIC_SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

# Google AI
GOOGLE_AI_API_KEY=

# Binance (Fase 2) - Router de entorno
BINANCE_ENV=spot_testnet  # spot_testnet | demo_futures
TRADING_ENABLED=false     # Kill switch global

# Spot Testnet
BINANCE_SPOT_BASE_URL=https://testnet.binance.vision
BINANCE_SPOT_WS_URL=wss://stream.testnet.binance.vision/ws

# Futures Demo (si se habilita perps)
BINANCE_FUTURES_BASE_URL=https://demo-fapi.binance.com
BINANCE_FUTURES_WS_URL=wss://fstream.binancefuture.com

# Credenciales (nunca en frontend)
BINANCE_API_KEY=
BINANCE_API_SECRET=

# HITL (Fase 2)
AUTO_APPROVE_THRESHOLD_USDT=100
HITL_SLA_SECONDS=300
HITL_NOTIFICATIONS=push,email

# Broker Adapter (Fase 2)
BROKER_ADAPTER=simulated  # simulated | spot_testnet | demo_futures

# Circuit Breakers (Fase 2)
MAX_DAILY_LLM_COST_USD=5
MAX_CONSECUTIVE_LOSSES=3

# App
NEXT_PUBLIC_APP_URL=
```

### Proteccion contra Prompt Injection
- System prompt tiene instrucciones claras de formato de output
- Se usa `generateObject` con Zod schema (output estructurado, no free text)
- El LLM nunca ejecuta codigo directamente
- Risk manager es codigo determinista, no prompt

---

## 14. Testing

### Unit Tests (Vitest)
- Indicators engine (SMA, RSI, Bollinger calculations)
- Risk manager (limit validation)
- Chunking algorithm
- Schema validation

### Integration Tests
- Source Agent: evalua paper mock, verifica scores
- Reader Agent: extrae estrategia de texto mock
- Synthesis Agent: genera guia desde estrategias mock
- API routes: CRUD completo

### E2E Tests (Playwright)
- Agregar fuente desde UI
- Ver estrategias extraidas
- Chatear con el agente
- Generar guia

### Tests Fase 2 (Trading)

**Unit Tests:**
- Transicion de estados HITL (todos los caminos de la maquina de estados)
- Circuit breakers: activacion y desactivacion por cada tipo
- SimulatedBroker: fill con slippage, balance tracking, posiciones
- Idempotencia: doble submit con mismo client_order_id
- Reconciliacion: deteccion de divergencias (ordenes huerfanas, missing)

**Integration Tests:**
- Flujo completo: propuesta → auto-approve → ejecucion simulada → log
- Flujo HITL: propuesta → pending_approval → approve → ejecucion
- Flujo rechazo: propuesta → risk_rejected (por breaker activo)
- Reconciliacion contra SimulatedBroker con estado divergente
- Dead-letter: orden falla 3 veces → status dead_letter → alerta

**E2E Tests:**
- /approvals: ver propuesta pendiente, aprobar, verificar ejecucion
- /operations: verificar metricas y estado de breakers
- /simulator: configurar y ejecutar replay de datos historicos
- Propuesta → aprobacion → ejecucion simulada → aparece en /history

---

## 15. Deploy y CI/CD

### Vercel
- Push to main = deploy automatico
- Preview deployments en PRs
- Serverless functions para API routes (nota: procesos largos como embedding/extraccion deben correr como background jobs con cola async, no en request-response directo por timeout de serverless)

### Supabase
- Migrations con Supabase CLI
- Seed data para desarrollo

### CI Pipeline (GitHub Actions)
```
1. Lint (ESLint)
2. Type check (tsc)
3. Unit tests (Vitest)
4. Build (next build)
5. Deploy preview (Vercel)
```

---

## 16. Roadmap Detallado

### Semana 1: Foundation + Hardening P0
- [ ] Crear proyecto Next.js 16 desde cero
- [ ] Fijar `engines: { "node": ">=20.9.0" }` en package.json
- [ ] Configurar Tailwind CSS 4
- [ ] Setup Supabase (proyecto + tablas + pgvector + RLS basico)
- [ ] Ejecutar migrations SQL (con HNSW index y UNIQUE constraints)
- [ ] Configurar Vercel AI SDK con Gemini (`@ai-sdk/google` + `gemini-2.5-flash`)
- [ ] Implementar fetcher seguro con proteccion SSRF (allowlist, bloqueo IPs privadas, timeouts)
- [ ] Crear estructura de carpetas (lib, components, api routes)
- [ ] Setup cola async para jobs largos (embedding/extraccion)
- [ ] Deploy inicial a Vercel

### Semana 2: Source Agent + Reader Agent
- [ ] Implementar Source Agent (con fetcher seguro)
- [ ] Implementar Reader Agent (sobre cola async, no sync API)
- [ ] Implementar chunking + embeddings (pgvector)
- [ ] API routes: sources CRUD + evaluate + process
- [ ] Cargar 5-10 papers iniciales de prueba
- [ ] Verificar que el pipeline funciona end-to-end

### Semana 3: Synthesis Agent + Dashboard
- [ ] Implementar Synthesis Agent
- [ ] API routes: guides generate + current + history
- [ ] Dashboard: Overview page
- [ ] Dashboard: Sources page (tabla + agregar)
- [ ] Dashboard: Strategies page (tabla)
- [ ] Dashboard: Guide page (render markdown)
- [ ] Chat: implementar con useChat() + RAG

### Semana 4: Polish + Preparar Fase 2
- [ ] Re-analisis automatico (cron job o webhook)
- [ ] Mejorar UI (loading states, error handling)
- [ ] Testing (unit + integration)
- [ ] Documentacion
- [ ] Preparar estructura para Fase 2 (trading)

---

## 17. Estructura de Archivos

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
      # --- Fase 2 ---
      proposals/
        route.ts                      # POST create, GET list
        [id]/
          route.ts                    # GET detail
          approve/route.ts            # POST approve
          reject/route.ts             # POST reject
      orders/
        route.ts                      # GET list
        [id]/route.ts                 # GET detail
      reconciliation/
        run/route.ts                  # POST trigger
        history/route.ts              # GET history
        latest/route.ts               # GET latest
      risk/
        breakers/route.ts             # GET status + history
        breakers/[name]/resolve/route.ts # POST resolve
      operations/
        metrics/route.ts              # GET KPIs
        pnl/route.ts                  # GET PnL
        health/route.ts               # GET health check
      simulator/
        config/route.ts               # POST config
        replay/route.ts               # POST start replay
        status/route.ts               # GET status
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
      indicators.ts                   # Technical indicators (Fase 2)
      risk-manager.ts                 # Risk limits (Fase 2)
      circuit-breakers.ts             # Circuit breakers avanzados (Fase 2)
      fetcher.ts                      # URL content fetcher
    trading/                          # Fase 2
      broker-adapter.ts               # Interface BrokerAdapter
      simulated-broker.ts             # Broker simulado local
      binance-spot-testnet.ts         # Adapter Binance Spot Testnet
      binance-futures-demo.ts         # Adapter Binance Futures Demo
      proposal-workflow.ts            # Maquina de estados TradeProposal
      reconciliation.ts               # Reconciliacion periodica
      replay-engine.ts                # Replay de datos historicos
  components/
    ui/                               # Shared UI components
    sources/                          # Source-specific components
    strategies/                       # Strategy-specific components
    guide/                            # Guide-specific components
    chat/                             # Chat components
    dashboard/                        # Dashboard widgets
    approvals/                        # HITL approval queue (Fase 2)
    operations/                       # Operations center (Fase 2)
    simulator/                        # Simulator config + replay (Fase 2)
    trading/                          # Live trading dashboard (Fase 2)
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

---

## 18. Registro de Auditoria CODEX (2026-02-15)

Este plan fue auditado por Codex (ver `/CODEX/`) y las siguientes correcciones P0 fueron aplicadas:

| # | Correccion | Estado |
|---|---|---|
| 1 | Migrar `@google/generative-ai` → `@ai-sdk/google` (SDK deprecado) | Aplicado |
| 2 | Migrar `gemini-2.0-flash` → `gemini-2.5-flash` (shutdown 2026-03-31) | Aplicado |
| 3 | Corregir API embedding: `textEmbeddingModel()` → `embedding()` (AI SDK v6) | Aplicado |
| 4 | Corregir WS Binance Spot: usar `stream.testnet.binance.vision` (legacy deprecado) | Aplicado |
| 5 | Separar Spot Testnet y Futures Demo con router de entorno | Aplicado |
| 6 | Fix bug `extractionId` undefined → capturar ID del insert con `.select('id')` | Aplicado |
| 7 | Cambiar IVFFlat → HNSW para pgvector (mejor para datasets chicos) | Aplicado |
| 8 | Agregar `UNIQUE` constraint en `trading_guides.version` | Aplicado |
| 9 | Endurecer fetcher contra SSRF (allowlist, bloqueo IPs privadas, timeouts) | Aplicado |
| 10 | Habilitar RLS desde MVP (no esperar a auth) | Aplicado |
| 11 | Mover procesos largos a background jobs (no request-response) | Aplicado |
| 12 | Agregar requisito Node.js >= 20.9.0 en `engines` | Aplicado |
| 13 | Corregir costeo embeddings a pricing oficial vigente | Aplicado |

### Ronda 2: CODEX/10-cambios-sugeridos-finales.md (2026-02-15)

| # | Correccion | Estado |
|---|---|---|
| 14 | Migrar `text-embedding-004` → `gemini-embedding-001` (modelo apagado 2026-01-14) | Aplicado |
| 15 | Actualizar VECTOR(768) → VECTOR(1024) en schema SQL y RPC | Aplicado |
| 16 | Agregar `providerOptions.google.outputDimensionality: 1024` en embed() calls | Aplicado |
| 17 | Agregar RLS concreto: ENABLE + politicas service_role en todas las tablas | Aplicado |
| 18 | Agregar campos de cost tracking en agent_logs (`tokens_input`, `tokens_output`, `estimated_cost_usd`) | Aplicado |
| 19 | Agregar nota de map-reduce para Reader Agent en papers largos | Aplicado |

> **Nota:** El snippet 4.1 del audit CODEX/10 tenia un error de sintaxis:
> `google.embedding('gemini-embedding-001', { outputDimensionality: 1024 })` es incorrecto.
> La sintaxis correcta de AI SDK v6 usa `providerOptions` en la llamada a `embed()`, no en el constructor del modelo.

### Ronda 3: CODEX/12 + deep-research-report (2) — Fase 2 Trading Bot (2026-02-15)

| # | Feature agregada | Scope |
|---|---|---|
| 20 | HITL Workflow hibrido (auto < $100, manual >= $100, push notifications, SLA 5 min) | Seccion 12.6 |
| 21 | SimulatedBroker adapter con replay de datos historicos + criterio graduacion | Seccion 12.7 |
| 22 | Circuit Breakers avanzados: trading + infra + LLM (7 breakers, acciones por tipo) | Seccion 12.8 |
| 23 | Reconciliacion periodica (60s) + idempotencia con client_order_id + dead-letter | Seccion 12.9 |
| 24 | Logs inmutables con correlation_id + metricas operativas (10 KPIs) | Seccion 12.10 |
| 25 | 4 tablas SQL nuevas: trade_proposals, execution_orders, reconciliation_runs, risk_breaker_events | Seccion 12.11 |
| 26 | 17 API routes nuevas para proposals, orders, reconciliation, risk, operations, simulator | Seccion 12.12 |
| 27 | 5 paginas frontend nuevas: /approvals, /trading, /operations, /history, /simulator | Seccion 12.13 |
| 28 | Roadmap Fase 2 detallado: Semanas 5-12 | Seccion 12.15 |
| 29 | Definition of Done Fase 2 (11 criterios) | Seccion 12.16 |
| 30 | Tests Fase 2: unit + integration + e2e para HITL, breakers, reconciliacion, simulador | Seccion 14 |
| 31 | File structure actualizada con lib/trading/, components/approvals, etc. | Seccion 17 |

> **Decisiones de diseno tomadas (brainstorming):**
> - HITL hibrido en vez de full-approval (pragmatico para MVP)
> - Logs inmutables simples en vez de hash chain (YAGNI para MVP)
> - Simulador con replay historico antes de exchange (mas seguro)
> - Circuit breakers avanzados (incluyen infra y LLM, no solo trading)
> - LangGraph descartado — Vercel AI SDK se mantiene como decision previa
> - IVFFlat del report descartado — HNSW se mantiene (decision ronda 1)
> - text-embeddings-002 de OpenAI descartado — gemini-embedding-001 se mantiene (decision ronda 2)

### P1 pendientes (post-Semana 1)
- Evaluacion RAG offline para calibrar `match_threshold` (actualmente fijo en 0.7)
- Instrumentar observabilidad de costos y latencias por agente (campos ya en schema)
- Suite de pruebas contractuales para prompts JSON
- Implementar map-reduce completo para Reader Agent (reemplazar `slice()` por procesamiento por secciones)
- Control de contexto en Synthesis: no serializar arrays completos, usar top-N + resumen por lotes

### Fuentes de la auditoria
- Gemini deprecations: https://ai.google.dev/gemini-api/docs/deprecations
- Gemini JS SDK: https://github.com/googleapis/js-genai
- AI SDK v6 migration: https://ai-sdk.dev/docs/migration-guides/migration-guide-6-0
- AI SDK Google provider embeddings: https://ai-sdk.dev/providers/ai-sdk-providers/google-generative-ai
- Gemini embedding model: https://ai.google.dev/gemini-api/docs/embeddings
- Binance Spot Testnet WS: https://developers.binance.com/docs/binance-spot-api-docs/testnet/web-socket-streams
- Binance Futures Demo: https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info
- pgvector HNSW: https://github.com/pgvector/pgvector
- Supabase RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
