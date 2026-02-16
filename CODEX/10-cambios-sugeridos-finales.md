# Cambios Sugeridos Finales (Version Ejecutable)

Fecha: 2026-02-15  
Documento base: `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md`  
Estado recomendado: `GO condicionado` (cerrar P0 primero)

## 1. Resumen ejecutivo

El plan mejoro mucho y ya tiene correcciones importantes aplicadas.  
Para dejarlo realmente ejecutable sin riesgos altos, quedan 2 P0 tecnicos y 4 P1.

P0 abiertos:
1. Migrar embeddings de `text-embedding-004` a un modelo vigente (`gemini-embedding-001`).
2. Alinear costos y arquitectura al modelo de embedding vigente (evitar incoherencia entre registro y implementacion).

## 2. Cambios P0 obligatorios

### P0-1: Migracion de embeddings a modelo vigente

Problema:
- El plan aun referencia `text-embedding-004` en varios puntos.
- Ese modelo figura con retiro anunciado en documentacion oficial.

Cambio requerido:
1. Cambiar modelo por `gemini-embedding-001`.
2. Definir dimensionalidad objetivo (recomendado 1024 para balance costo/calidad).
3. Actualizar schema SQL y RPC para que la dimension sea consistente.
4. Re-embed de datos existentes con job de migracion.

Impacto en el plan:
- Secciones de AI SDK, RAG y SQL (`paper_chunks.embedding VECTOR(...)`).
- Scripts de carga/reprocesamiento.

### P0-2: Coherencia de costo y operacion

Problema:
- El registro indica costo corregido, pero la implementacion de embedding no esta cerrada.

Cambio requerido:
1. Dejar costos como "pricing oficial vigente" + fecha de consulta.
2. Agregar metrica real de consumo por agente:
   - tokens input/output
   - costo estimado por llamada
   - costo acumulado diario
3. Agregar alertas por presupuesto diario.

## 3. Cambios P1 inmediatos (post P0)

1. Evitar truncamiento bruto:
- Reemplazar `slice(15000)` y `slice(30000)` por estrategia map-reduce:
  - map por seccion/chunk
  - reduce de hallazgos estructurados

2. Calibrar RAG:
- `match_threshold` no debe quedar fijo sin evaluacion offline.
- Correr benchmark con precision@k y recall@k sobre preguntas de control.

3. Control de contexto en synthesis:
- No serializar arrays completos de estrategias/extractions en un solo prompt.
- Aplicar top-N + resumen intermedio por lotes.

4. RLS concreto:
- No dejarlo solo como principio.
- Definir politicas SQL minimas desde MVP.

## 4. Cambios tecnicos concretos (snippets sugeridos)

### 4.1 AI SDK embedding (actualizado)

```ts
import { embed } from 'ai';
import { google } from '@/lib/ai';

const { embedding } = await embed({
  model: google.embedding('gemini-embedding-001', {
    outputDimensionality: 1024,
  }),
  value: text,
});
```

### 4.2 SQL vector dimension

```sql
ALTER TABLE paper_chunks
  ALTER COLUMN embedding TYPE vector(1024);
```

Si ya hay datos:
1. Crear columna temporal `embedding_new vector(1024)`.
2. Re-embed por lotes.
3. Switchear columnas y reconstruir indice HNSW.

### 4.3 RLS minimo recomendado

```sql
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategies_found ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE trading_guides ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
```

Luego crear politicas explicitas para rol de servicio y (si aplica) usuario autenticado.

## 5. Incorporacion MCP Binance (decision final)

Decision:
- `SI`, incorporar MCP para acelerar testing simulado.
- Arquitectura recomendada: MCP para market data + adapter determinista separado para ejecucion.

### 5.1 Modo inicial (seguro)

Habilitar solo read-only:
- `get_server_time`
- `get_ticker`
- `get_order_book`
- `get_open_orders`
- `get_positions` (si disponible)

Bloquear al inicio:
- `place_order`
- `cancel_order`

### 5.2 Modo ejecucion demo

Router por entorno:
- Spot testnet:
  - REST: `https://testnet.binance.vision`
  - WS: `wss://stream.testnet.binance.vision/ws`
- Futures demo:
  - REST: `https://demo-fapi.binance.com`
  - WS: `wss://fstream.binancefuture.com`

Guardrails obligatorios:
1. `TRADING_ENABLED=false` por default.
2. Rechazar orden si `BINANCE_ENV` no es valido.
3. Solo `BTCUSDT` en fase inicial.
4. Max notional y max posiciones desde codigo determinista.
5. Kill-switch por errores consecutivos.

## 6. Variables de entorno finales sugeridas

```env
# Core
GOOGLE_AI_API_KEY=
NEXT_PUBLIC_SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

# Binance router
BINANCE_ENV=spot_testnet   # spot_testnet | demo_futures
TRADING_ENABLED=false

# Spot testnet
BINANCE_SPOT_BASE_URL=https://testnet.binance.vision
BINANCE_SPOT_WS_URL=wss://stream.testnet.binance.vision/ws

# Futures demo
BINANCE_FUTURES_BASE_URL=https://demo-fapi.binance.com
BINANCE_FUTURES_WS_URL=wss://fstream.binancefuture.com

# Credenciales
BINANCE_API_KEY=
BINANCE_API_SECRET=
```

## 7. Plan de ejecucion (7 dias)

Dia 1:
- Migrar embedding model y dimension vector.
- Ajustar snippets AI SDK/RAG/SQL.

Dia 2:
- Job de re-embedding por lotes + rebuild HNSW.
- Validacion de consultas RPC.

Dia 3:
- Implementar metricas de costo/tokens/latencia por agente.
- Alertas de presupuesto.

Dia 4:
- Map-reduce para Reader y control de contexto en Synthesis.

Dia 5:
- RLS policies minimas y tests de acceso.

Dia 6:
- Integrar MCP Binance read-only + smoke tests.

Dia 7:
- Activar adapter de ejecucion demo con kill-switch y limites.
- E2E de pipeline completo en entorno simulado.

## 8. Criterio de cierre (Definition of Done)

P0 cerrado cuando:
1. No queda referencia activa a `text-embedding-004`.
2. Embeddings, schema y RPC usan dimension consistente.
3. Metricas de costo reales estan visibles por agente.
4. Smoke test RAG pasa con modelo vigente.

P1 cerrado cuando:
1. Reader no depende de truncamiento por `slice`.
2. `match_threshold` calibrado con dataset de evaluacion.
3. Synthesis opera con batching/control de contexto.
4. RLS tiene politicas activas y testeadas.

## 9. Nota final

Con estos ajustes, el plan pasa de "correcto en arquitectura" a "ejecutable con riesgo controlado" para MVP institucional.
