# Fase 0: Foundation + Cierre P0

**Proyecto:** traiding-agentic
**Duracion:** Semana 1
**Prerequisitos:** Ninguno
**Estado:** Plan final validado
**Fecha:** 2026-02-15

---

## 1. Objetivo

Crear el proyecto desde cero con el stack correcto, cerrar todos los P0 del CODEX, y dejar la infraestructura lista para que Fase 1 solo escriba logica de negocio.

## 2. Decisiones Tecnicas Cerradas

| Decision | Valor | Origen |
|---|---|---|
| Framework | Next.js 16 + React 19 | CODEX 13 |
| Styling | Tailwind CSS 4 | Plan tecnico |
| Runtime | Node.js >= 20.9.0 (fijar en engines) | CODEX 13 |
| Package manager | pnpm | Plan tecnico |
| LLM | gemini-2.5-flash via @ai-sdk/google | CODEX ronda 1 |
| Embeddings | gemini-embedding-001, 1024 dims | CODEX ronda 2 |
| DB | Supabase PostgreSQL + pgvector | Plan tecnico |
| Vector index | HNSW (m=16, ef_construction=64) | CODEX ronda 1 |
| Cola async | Vercel Background Functions | Decision usuario |
| Notificaciones | Telegram Bot (t.me/Traiding77bot) | Decision usuario |
| Hosting | Vercel (serverless) | Plan tecnico |
| Codebase anterior | Borrar /frontend (Next.js 14 viejo) | Decision usuario |

## 3. Entregables

### 3.1 Proyecto base

- [ ] Borrar directorio `/frontend` existente (Next.js 14 + React 18)
- [ ] Crear proyecto Next.js 16 en la raiz con App Router
- [ ] Configurar React 19 + TypeScript 5.x
- [ ] Configurar Tailwind CSS 4
- [ ] Fijar `engines: { "node": ">=20.9.0" }` en package.json
- [ ] Fijar versiones exactas de dependencias core (no "latest"):
  - `next` (version exacta 16.x)
  - `react` / `react-dom` (version exacta 19.x)
  - `ai` (Vercel AI SDK, version exacta)
  - `@ai-sdk/google` (version exacta)
  - `@supabase/supabase-js` (version exacta)
  - `zod` (version exacta)
  - `swr` (version exacta 2.x)
- [ ] Configurar ESLint + Prettier
- [ ] Crear `pnpm-lock.yaml` y verificar `pnpm install --frozen-lockfile`
- [ ] Crear `.env.example` con todas las variables (sin valores reales)

### 3.2 Estructura de carpetas

```
traiding-agentic/
  app/
    layout.tsx
    page.tsx                          # Placeholder overview
    globals.css
    api/                              # API routes (vacias, estructura)
  lib/
    supabase.ts                       # Supabase client (server + browser)
    ai.ts                             # Vercel AI SDK setup (gemini + embedding)
    agents/
      prompts.ts                      # System prompts (placeholder)
    utils/
      fetcher.ts                      # URL content fetcher (SSRF-safe)
      telegram.ts                     # Telegram Bot wrapper
  components/
    ui/                               # Shared UI components
  supabase/
    migrations/
      001_initial_schema.sql          # Tablas Fase 1 + RLS + indices
      002_pgvector_setup.sql          # pgvector extension + match_chunks RPC
    seed.sql                          # Seed data para dev
  public/
  .env.local                          # Variables reales (gitignored)
  .env.example                        # Template de variables
  next.config.ts
  package.json
  tsconfig.json
  tailwind.config.ts
```

### 3.3 Supabase: Schema completo Fase 1

Ejecutar migrations con todas las tablas necesarias para Fase 1:

**001_initial_schema.sql:**

```sql
-- sources
CREATE TABLE sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  url TEXT NOT NULL UNIQUE,
  title TEXT,
  authors TEXT,
  publication_year INTEGER,
  source_type TEXT CHECK (source_type IN ('paper', 'article', 'repo', 'book', 'video')) NOT NULL,
  relevance_score INTEGER CHECK (relevance_score BETWEEN 1 AND 10),
  credibility_score INTEGER CHECK (credibility_score BETWEEN 1 AND 10),
  applicability_score INTEGER CHECK (applicability_score BETWEEN 1 AND 10),
  overall_score INTEGER CHECK (overall_score BETWEEN 1 AND 10),
  tags TEXT[] DEFAULT '{}',
  summary TEXT,
  evaluation_reasoning TEXT,
  status TEXT CHECK (status IN (
    'pending', 'evaluating', 'approved', 'processing',
    'processed', 'rejected', 'error'
  )) DEFAULT 'pending',
  rejection_reason TEXT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  evaluated_at TIMESTAMPTZ,
  processed_at TIMESTAMPTZ
);

CREATE INDEX idx_sources_status ON sources(status);
CREATE INDEX idx_sources_overall_score ON sources(overall_score DESC);
CREATE INDEX idx_sources_tags ON sources USING GIN(tags);

-- paper_extractions
CREATE TABLE paper_extractions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  strategies JSONB DEFAULT '[]',
  key_insights TEXT[] DEFAULT '{}',
  risk_warnings TEXT[] DEFAULT '{}',
  market_conditions TEXT[],
  data_period TEXT,
  sample_size TEXT,
  contradicts JSONB DEFAULT '[]',
  supports JSONB DEFAULT '[]',
  raw_summary TEXT,
  executive_summary TEXT,
  confidence_score INTEGER CHECK (confidence_score BETWEEN 1 AND 10),
  processing_model TEXT,
  processing_tokens INTEGER,
  processed_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_extractions_source ON paper_extractions(source_id);
CREATE INDEX idx_extractions_confidence ON paper_extractions(confidence_score DESC);

-- strategies_found
CREATE TABLE strategies_found (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  extraction_id UUID NOT NULL REFERENCES paper_extractions(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  strategy_type TEXT CHECK (strategy_type IN (
    'momentum', 'mean_reversion', 'breakout', 'trend_following',
    'statistical_arbitrage', 'market_making', 'sentiment',
    'machine_learning', 'hybrid', 'other'
  )),
  market TEXT DEFAULT 'btc',
  timeframe TEXT,
  indicators TEXT[] DEFAULT '{}',
  entry_rules TEXT[] DEFAULT '{}',
  exit_rules TEXT[] DEFAULT '{}',
  position_sizing TEXT,
  backtest_results JSONB DEFAULT '{}',
  limitations TEXT[] DEFAULT '{}',
  best_market_conditions TEXT[],
  worst_market_conditions TEXT[],
  confidence INTEGER CHECK (confidence BETWEEN 1 AND 10),
  evidence_strength TEXT CHECK (evidence_strength IN ('weak', 'moderate', 'strong')),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_strategies_type ON strategies_found(strategy_type);
CREATE INDEX idx_strategies_market ON strategies_found(market);
CREATE INDEX idx_strategies_confidence ON strategies_found(confidence DESC);
CREATE INDEX idx_strategies_indicators ON strategies_found USING GIN(indicators);

-- trading_guides
CREATE TABLE trading_guides (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  version INTEGER NOT NULL UNIQUE,
  based_on_sources INTEGER NOT NULL,
  based_on_strategies INTEGER NOT NULL,
  sources_used UUID[] DEFAULT '{}',
  primary_strategy JSONB NOT NULL,
  secondary_strategies JSONB DEFAULT '[]',
  market_conditions_map JSONB DEFAULT '{}',
  avoid_list TEXT[] DEFAULT '{}',
  risk_parameters JSONB DEFAULT '{}',
  full_guide_markdown TEXT NOT NULL,
  system_prompt TEXT NOT NULL,
  executive_summary TEXT,
  confidence_score INTEGER CHECK (confidence_score BETWEEN 1 AND 10),
  limitations TEXT[] DEFAULT '{}',
  changes_from_previous TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_guides_version ON trading_guides(version DESC);

-- agent_logs
CREATE TABLE agent_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name TEXT NOT NULL CHECK (agent_name IN ('source', 'reader', 'synthesis', 'trading', 'chat')),
  action TEXT NOT NULL,
  source_id UUID REFERENCES sources(id),
  input_summary TEXT,
  output_summary TEXT,
  reasoning TEXT,
  tokens_input INTEGER,
  tokens_output INTEGER,
  tokens_used INTEGER,
  duration_ms INTEGER,
  model_used TEXT,
  estimated_cost_usd NUMERIC(10,6),
  status TEXT CHECK (status IN ('started', 'success', 'error', 'warning')),
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_logs_agent ON agent_logs(agent_name);
CREATE INDEX idx_logs_created ON agent_logs(created_at DESC);
CREATE INDEX idx_logs_source ON agent_logs(source_id);

-- chat_messages
CREATE TABLE chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  role TEXT CHECK (role IN ('user', 'assistant', 'system')) NOT NULL,
  content TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_chat_created ON chat_messages(created_at DESC);

-- RLS en todas las tablas
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategies_found ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE trading_guides ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- Politicas service_role (backend)
CREATE POLICY "service_role_full_access" ON sources FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON paper_extractions FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON strategies_found FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON paper_chunks FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON trading_guides FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON agent_logs FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON chat_messages FOR ALL USING (true);
```

**002_pgvector_setup.sql:**

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE paper_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  section_title TEXT,
  page_number INTEGER,
  embedding VECTOR(1024),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_chunks_embedding ON paper_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_chunks_source ON paper_chunks(source_id);
CREATE INDEX idx_chunks_metadata ON paper_chunks USING GIN(metadata);

-- RPC para busqueda vectorial
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

### 3.4 AI SDK Setup

```typescript
// lib/ai.ts
import { createGoogleGenerativeAI } from '@ai-sdk/google';

export const google = createGoogleGenerativeAI({
  apiKey: process.env.GOOGLE_AI_API_KEY,
});

export const gemini = google('gemini-2.5-flash');
```

Smoke test de embedding:

```typescript
import { embed } from 'ai';
import { google } from '@/lib/ai';

const { embedding } = await embed({
  model: google.embedding('gemini-embedding-001'),
  value: 'test de embedding para trading',
  providerOptions: {
    google: { outputDimensionality: 1024 },
  },
});
// Verificar: embedding.length === 1024
```

### 3.5 Fetcher SSRF-safe

```typescript
// lib/utils/fetcher.ts
// Implementar:
// - Validacion de URL (solo http/https)
// - Bloqueo de IPs privadas (10.x, 172.16-31.x, 192.168.x, 169.254.x)
// - Bloqueo de metadata endpoints (169.254.169.254)
// - Timeout: 10 segundos
// - Max response size: 5MB
// - Content-type whitelist: text/html, text/plain, application/pdf, application/json
// - Seguir redirects (max 3)
// - User-Agent personalizado
```

### 3.6 Telegram Bot Wrapper

```typescript
// lib/utils/telegram.ts
// Wrapper minimo sobre Telegram Bot API:
// - sendMessage(chatId, text) - enviar mensaje
// - sendAlert(text) - enviar al chat del operador (TELEGRAM_CHAT_ID)
// Variables de entorno:
//   TELEGRAM_BOT_TOKEN=<token>
//   TELEGRAM_CHAT_ID=<chat_id del operador>
```

### 3.7 Vercel Background Functions

- [ ] Configurar `vercel.json` con `maxDuration` para funciones que lo necesiten
- [ ] Crear helper `lib/utils/background.ts` para lanzar jobs async
- [ ] Job de ejemplo: fetch URL + generar embedding + guardar en pgvector

### 3.8 CI/CD

- [ ] GitHub Actions workflow basico:
  1. `pnpm install --frozen-lockfile`
  2. `pnpm lint`
  3. `pnpm tsc --noEmit`
  4. `pnpm build`
- [ ] Deploy automatico a Vercel en push a main
- [ ] Preview deployments en PRs

### 3.9 Variables de Entorno

```env
# .env.example

# Core
GOOGLE_AI_API_KEY=
NEXT_PUBLIC_SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# App
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## 4. Gate de Salida (Fase 0 → Fase 1)

Todas estas condiciones deben cumplirse antes de iniciar Fase 1:

- [ ] `pnpm install --frozen-lockfile` pasa sin errores
- [ ] `pnpm lint && pnpm tsc --noEmit` pasa sin errores
- [ ] `pnpm build` genera build exitoso
- [ ] Smoke SQL: INSERT + SELECT + RPC match_chunks funcionan en Supabase
- [ ] Test embedding: genera vector de 1024 dimensiones y se almacena correctamente
- [ ] Test RLS: conexion con anon key NO puede leer tablas internas
- [ ] Test fetcher: URL valida pasa, IP privada se bloquea, timeout funciona
- [ ] Test Telegram: mensaje "Sistema iniciado" llega al chat del operador
- [ ] Deploy a Vercel exitoso y accesible
- [ ] CI pipeline verde en GitHub Actions

## 5. Definition of Done

Fase 0 esta completa cuando:

1. No quedan referencias a Next.js 14, React 18 ni al directorio `/frontend` viejo
2. Todas las tablas de Fase 1 existen en Supabase con RLS + politicas
3. pgvector funciona con HNSW index y RPC match_chunks
4. AI SDK genera embeddings de 1024 dims con gemini-embedding-001
5. Fetcher SSRF-safe rechaza destinos peligrosos
6. Telegram Bot envia mensajes correctamente
7. Vercel Background Functions ejecutan un job de ejemplo
8. Build reproducible en local y CI

## 6. Riesgos y Mitigaciones

| Riesgo | Mitigacion |
|---|---|
| Next.js 16 no esta estable | Verificar release notes, tener fallback a 15.x si hay blocker |
| Supabase pgvector no soporta HNSW | Verificar version de pgvector >= 0.5.0 en el proyecto |
| Vercel Background Functions con limite de tiempo | Verificar tier del plan, considerar chunking de jobs largos |
| Telegram API rate limits | Implementar retry con backoff, no enviar mas de 1 msg/seg |
