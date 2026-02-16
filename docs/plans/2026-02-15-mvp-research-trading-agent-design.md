# MVP: Research Trading Agent - Design Document

**Fecha:** 2026-02-15
**Estado:** Aprobado
**Stack:** Next.js 16, Vercel AI SDK, Supabase + pgvector, Gemini

---

## 1. Vision General

Construir un sistema de agentes de investigacion que:
1. Recolecta y evalua fuentes de trading (papers, articulos, repos)
2. Extrae estrategias y conocimiento estructurado de cada fuente
3. Sintetiza toda la informacion en una "guia maestra" de trading
4. Alimenta un trading bot que opera en Binance Testnet (paper trading BTC)

El sistema se re-analiza periodicamente para refinar/cambiar estrategias.

### Dos Fases

**Fase 1 (este MVP): Research Agent**
- Source Agent + Reader Agent + Synthesis Agent
- Dashboard para ver fuentes, estrategias extraidas, y guia generada
- Chat para interactuar con el agente

**Fase 2 (siguiente): Trading Bot**
- Conecta a Binance Testnet via WebSocket
- Usa la guia maestra como system prompt + RAG
- Ejecuta trades con risk manager determinista
- Dashboard con KPIs de performance

---

## 2. Arquitectura

```
Fuentes (papers PDF, articulos, repos GitHub)
         |
         v
   Source Agent --- "Evalua relevancia, credibilidad, aplicabilidad"
         |
         v
   Supabase: tabla `sources` (url, title, score, status)
         |
         v
   Reader Agent --- "Lee paper, extrae estrategias e insights"
         |
         v
   Supabase: tabla `paper_extractions` + `strategies_found`
   pgvector: embeddings de chunks del paper (para RAG)
         |
         v
   Synthesis Agent --- "Cruza todo, resuelve contradicciones, rankea"
         |
         v
   Supabase: tabla `trading_guides` (guia maestra versionada)
         |
         v
   Dashboard + Chat (Next.js 16 en Vercel)
         |
         v
   (Fase 2) Trading Bot --- usa guia como system prompt
```

### Stack Tecnologico

| Componente | Tecnologia |
|-----------|------------|
| Frontend | Next.js 16 (App Router) |
| Agentes | Vercel AI SDK |
| LLM | Gemini (Google) |
| Base de datos | Supabase (PostgreSQL) |
| Vector store | pgvector (extension de Supabase) |
| Deploy | Vercel |
| PDF parsing | pypdf / pdf-parse (JS) |
| Embeddings | Gemini embeddings o OpenAI text-embedding-3-small |

---

## 3. Agente 1: Source Agent (Curador de Fuentes)

### Responsabilidad
Evaluar y catalogar fuentes de informacion de trading.

### Input
- URLs de papers (arXiv, SSRN, Google Scholar)
- Repositorios de GitHub
- Articulos de blogs reconocidos

### Criterios de Evaluacion
- **Relevancia:** Habla de BTC/crypto o trading generico aplicable?
- **Credibilidad:** Peer review? Citas? Autor reconocido?
- **Aplicabilidad:** Se puede implementar con ~$10K capital, timeframe intraday/swing?
- **Actualidad:** Datos de mercado recientes (post-2020 preferible)?

### Output
Registro en tabla `sources`:

```sql
CREATE TABLE sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  url TEXT NOT NULL,
  title TEXT,
  authors TEXT,
  source_type TEXT CHECK (source_type IN ('paper', 'article', 'repo', 'book')),
  relevance_score INTEGER CHECK (relevance_score BETWEEN 1 AND 10),
  credibility_score INTEGER CHECK (credibility_score BETWEEN 1 AND 10),
  applicability_score INTEGER CHECK (applicability_score BETWEEN 1 AND 10),
  overall_score INTEGER CHECK (overall_score BETWEEN 1 AND 10),
  tags TEXT[], -- ['momentum', 'btc', 'mean-reversion', etc.]
  summary TEXT,
  status TEXT CHECK (status IN ('pending', 'approved', 'processing', 'processed', 'rejected')) DEFAULT 'pending',
  rejection_reason TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

### Flujo MVP
1. El usuario carga URLs manualmente (5-10 para empezar)
2. El Source Agent evalua cada una con Gemini
3. Las aprobadas (score >= 6) pasan a status 'approved'
4. El Reader Agent las procesa

---

## 4. Agente 2: Reader Agent (Extractor de Conocimiento)

### Responsabilidad
Leer papers/fuentes aprobadas y extraer informacion estructurada.

### Proceso
1. Descarga el PDF/pagina web
2. Convierte a texto
3. Divide en chunks (~500 tokens)
4. Genera embeddings de cada chunk -> pgvector
5. Pasa el paper completo a Gemini para extraccion estructurada

### Output - Extraccion Estructurada

Tabla `paper_extractions`:

```sql
CREATE TABLE paper_extractions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID REFERENCES sources(id),
  strategies JSONB, -- array de estrategias encontradas
  key_insights TEXT[], -- insights principales
  contradictions JSONB, -- que contradice de otros papers
  supports JSONB, -- que confirma de otros papers
  raw_summary TEXT, -- resumen en texto libre
  confidence_score INTEGER CHECK (confidence_score BETWEEN 1 AND 10),
  processed_at TIMESTAMPTZ DEFAULT now()
);
```

Tabla `strategies_found`:

```sql
CREATE TABLE strategies_found (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID REFERENCES sources(id),
  extraction_id UUID REFERENCES paper_extractions(id),
  name TEXT NOT NULL,
  description TEXT,
  market TEXT, -- 'btc', 'crypto', 'equities', 'general'
  timeframe TEXT, -- '1m', '5m', '1h', '4h', '1d'
  indicators TEXT[], -- ['RSI', 'SMA', 'Bollinger', etc.]
  entry_rules TEXT[],
  exit_rules TEXT[],
  backtest_results JSONB, -- {sharpe, drawdown, period, etc.}
  limitations TEXT[],
  confidence INTEGER CHECK (confidence BETWEEN 1 AND 10),
  created_at TIMESTAMPTZ DEFAULT now()
);
```

Tabla para embeddings (pgvector):

```sql
CREATE TABLE paper_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID REFERENCES sources(id),
  chunk_index INTEGER,
  content TEXT,
  embedding VECTOR(768), -- dimension depende del modelo
  metadata JSONB, -- {section, page, etc.}
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON paper_chunks USING ivfflat (embedding vector_cosine_ops);
```

### Formato de Estrategia Extraida

```json
{
  "name": "Momentum con RSI adaptativo",
  "description": "Comprar cuando RSI cruza 30 de abajo hacia arriba con confirmacion de tendencia",
  "market": "btc",
  "timeframe": "4h",
  "indicators": ["RSI", "SMA", "Volume"],
  "entry_rules": ["RSI < 30 cruzando hacia arriba", "SMA_10 > SMA_50", "Volumen > promedio 20p"],
  "exit_rules": ["RSI > 70", "Stop-loss -2%", "Take-profit +4%"],
  "backtest_results": {
    "sharpe": 1.8,
    "max_drawdown": "12%",
    "win_rate": "62%",
    "period": "2019-2023",
    "sample_size": 450
  },
  "limitations": ["No funciona en mercados laterales", "Requiere volumen alto"],
  "confidence": 7
}
```

---

## 5. Agente 3: Synthesis Agent (Generador de Guia Maestra)

### Responsabilidad
Cruzar toda la informacion extraida y generar una guia de trading coherente.

### Cuando Corre
- Cada vez que se procesa un paper nuevo
- Manualmente cuando el usuario lo pide
- Periodicamente (configurable, ej: semanal)

### Proceso
1. **Busca patrones comunes:** "5 de 8 papers confirman X"
2. **Resuelve contradicciones:** Pesa por calidad de backtest, actualidad, y credibilidad
3. **Rankea estrategias:** Por evidencia acumulada
4. **Genera la guia:** Documento estructurado y versionado

### Output - Trading Guide

Tabla `trading_guides`:

```sql
CREATE TABLE trading_guides (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  version INTEGER NOT NULL,
  based_on_sources INTEGER, -- cantidad de fuentes analizadas
  based_on_strategies INTEGER, -- cantidad de estrategias encontradas
  primary_strategy JSONB, -- estrategia principal recomendada
  secondary_strategies JSONB, -- alternativas
  avoid_list TEXT[], -- cosas que NO hacer
  market_conditions_map JSONB, -- {trending: strategy_a, ranging: strategy_b}
  confidence_score INTEGER CHECK (confidence_score BETWEEN 1 AND 10),
  limitations TEXT[],
  full_guide TEXT, -- guia completa en markdown
  system_prompt TEXT, -- system prompt generado para el trading bot
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### Formato de la Guia

```markdown
# Trading Guide v{N}
## Basada en: {X} papers, {Y} estrategias

### Estrategia principal: {nombre}
- Por que: Respaldada por {N} papers. Sharpe promedio {X}.
- Cuando usarla: {condiciones de mercado}
- Indicadores: {lista}
- Entry: {reglas}
- Exit: {reglas}

### Estrategia secundaria: {nombre}
- Cuando usarla: {condiciones alternativas}
- Entry/Exit: {reglas}

### NO hacer (evidencia en contra):
- {lista de cosas a evitar con razon}

### Nivel de confianza: {N}/10
- Limitaciones: {lista}
```

---

## 6. Dashboard (Next.js 16 + Vercel)

### Pantalla: Overview
**KPIs en cards:**
- Total fuentes cargadas / aprobadas / procesadas
- Total estrategias encontradas
- Version actual de la guia maestra
- Confianza general

### Pantalla: Fuentes
- Tabla con todas las fuentes: titulo, tipo, score, status
- Boton para agregar nueva URL
- Ver detalle de cada fuente (resumen, tags, razon de rechazo)

### Pantalla: Estrategias
- Tabla con todas las estrategias extraidas de papers
- Filtros por indicador, timeframe, mercado
- Score de confianza y respaldo (cuantos papers la mencionan)

### Pantalla: Guia Maestra
- Render de la guia actual en markdown
- Historial de versiones
- Boton "Re-generar guia" para forzar re-sintesis

### Pantalla: Chat
- Interfaz conversacional con el agente
- Puede responder preguntas sobre:
  - "Que dicen los papers sobre momentum en BTC?"
  - "Cual es la estrategia mas respaldada?"
  - "Por que descartaste el paper X?"
  - "Cuando fue la ultima vez que se actualizo la guia?"

---

## 7. Fase 2 (Futuro): Trading Bot

Una vez que la Guia Maestra esta generada, el Trading Bot la usa como cerebro:

### Componentes
- **Market Data:** WebSocket a Binance Testnet, klines BTCUSDT 1min
- **Indicators Engine:** SMA, RSI, Bollinger, Volume (calculados en tiempo real)
- **Strategy Advisor (Gemini):** Recibe indicadores + guia maestra, decide accion
- **Risk Manager determinista:**
  - Perdida diaria max: -2% ($200)
  - Posicion max: 0.001 BTC (~$100) por orden
  - 1 posicion abierta a la vez
  - Stop-loss automatico: -1.5%
  - Take-profit automatico: +3%
- **Execution:** Ordenes LIMIT via ccxt a Binance Testnet

### Dashboard Trading (se agrega al existente)
- Precio BTC en vivo
- Ganancia del dia / Ganancia acumulada total
- Operaciones realizadas (tabla con ganadoras/perdedoras)
- Posicion abierta con P&L en tiempo real
- Win rate, ratio ganancia/perdida
- Log de decisiones del agente

---

## 8. Schema de Base de Datos Completo (Supabase)

```
sources
  ├── paper_extractions (1:N)
  │     └── strategies_found (1:N)
  ├── paper_chunks (1:N) -- para pgvector/RAG
  └── trading_guides (independiente, referencia sources por metadata)
```

Tablas adicionales:
- `agent_logs` - log de todas las decisiones/acciones de los agentes
- `chat_messages` - historial del chat

---

## 9. APIs (Backend Routes)

### Research
- `POST /api/sources` — agregar nueva fuente (URL)
- `GET /api/sources` — listar fuentes con filtros
- `POST /api/sources/:id/evaluate` — trigger Source Agent
- `POST /api/sources/:id/process` — trigger Reader Agent
- `GET /api/strategies` — listar estrategias extraidas
- `POST /api/guide/generate` — trigger Synthesis Agent
- `GET /api/guide/current` — obtener guia actual
- `GET /api/guide/history` — historial de guias

### Chat
- `POST /api/chat` — enviar mensaje al agente, recibe respuesta con streaming

### (Fase 2) Trading
- `GET /api/trading/status` — estado del bot
- `GET /api/trading/positions` — posiciones abiertas
- `GET /api/trading/orders` — historial de ordenes
- `GET /api/trading/performance` — KPIs de performance

---

## 10. Plan de Implementacion (orden sugerido)

### Semana 1: Foundation
1. Setup Next.js 16 + Vercel AI SDK
2. Setup Supabase (tablas + pgvector)
3. Crear schema de DB completo
4. Estructura de proyecto (app router, API routes)

### Semana 2: Source Agent + Reader Agent
5. Implementar Source Agent (evaluacion de fuentes)
6. Implementar Reader Agent (extraccion de papers)
7. Pipeline: URL -> evaluacion -> extraccion -> pgvector
8. Cargar 5-10 papers iniciales

### Semana 3: Synthesis Agent + Dashboard
9. Implementar Synthesis Agent (generacion de guia)
10. Dashboard: Overview, Fuentes, Estrategias, Guia
11. Chat basico con contexto RAG

### Semana 4: Polish + Fase 2 Prep
12. Re-analisis automatico
13. Mejorar UI del dashboard
14. Preparar integracion con Binance Testnet
