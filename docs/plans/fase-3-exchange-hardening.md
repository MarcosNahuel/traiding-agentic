# Fase 3: Exchange + Reconciliacion + Hardening

**Proyecto:** traiding-agentic
**Duracion:** Semanas 9-12 (4 semanas)
**Prerequisitos:** Fase 2 completa (gate de salida aprobado + 48h estable en simulador)
**Estado:** Plan final validado
**Fecha:** 2026-02-15

---

## 1. Objetivo

Conectar el sistema a Binance Testnet/Futures Demo real, implementar reconciliacion periodica, observabilidad avanzada, y ejecutar piloto de 7 dias para validar estabilidad antes de considerar graduacion. Esta fase transforma el simulador en un sistema paper-trading real contra el exchange.

## 2. Decisiones Tecnicas Cerradas

| Decision | Valor | Origen |
|---|---|---|
| Exchange Spot | Binance Spot Testnet (testnet.binance.vision) | CODEX 13 |
| Exchange Futures | Binance Futures Demo (demo-fapi.binance.com) | CODEX 13 |
| WS Spot | wss://stream.testnet.binance.vision/ws | CODEX ronda 1 |
| WS Futures | wss://fstream.binancefuture.com | CODEX ronda 1 |
| Reconciliacion | Cada 60 segundos | Plan tecnico |
| Dead-letter | 3 reintentos → dead_letter | Plan tecnico |
| Time sync | Sincronizar con servidor Binance + recvWindow | CODEX 13 |
| Graduacion | 7 dias estable, Sharpe>0, errors<1%, sin divergencias 48h | CODEX 13 |
| Filtros de simbolo | Validar con exchangeInfo antes de orden | CODEX 13 |
| MCP Binance | SI, read-only para market data (forgequant/mcp-provider-binance) | CODEX 03 |
| Kill switch | TRADING_ENABLED=false por default | CODEX 13 |

## 3. Modelo de Datos (nuevas tablas)

### Migration 004_reconciliation_schema.sql

```sql
-- Reconciliation Runs
CREATE TABLE reconciliation_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  broker_adapter TEXT NOT NULL,
  orders_synced INTEGER NOT NULL DEFAULT 0,
  positions_synced INTEGER NOT NULL DEFAULT 0,
  divergences_found INTEGER NOT NULL DEFAULT 0,
  divergence_details JSONB DEFAULT '[]',
  actions_taken JSONB DEFAULT '[]',
  balance_snapshot JSONB DEFAULT '{}',
  status TEXT CHECK (status IN ('running', 'success', 'error')) DEFAULT 'running',
  error_message TEXT,
  duration_ms INTEGER,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_recon_created ON reconciliation_runs(created_at DESC);
ALTER TABLE reconciliation_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_full_access" ON reconciliation_runs FOR ALL USING (true);
```

## 4. Entregables por Semana

### Semana 9: Binance Adapters + Market Data Real

#### 4.1 BinanceSpotTestnet Adapter

- [ ] Implementar `lib/trading/binance-spot-testnet.ts`
- [ ] Implementa la misma interface BrokerAdapter que SimulatedBroker
- [ ] REST base: `https://testnet.binance.vision`
- [ ] Autenticacion: HMAC-SHA256 con API key/secret
- [ ] Validacion runtime: rechazar si `BINANCE_ENV !== 'spot_testnet'`
- [ ] Time sync: obtener server time y calcular offset para `timestamp` + `recvWindow`
- [ ] Validacion de filtros: obtener `exchangeInfo` y aplicar LOT_SIZE, MIN_NOTIONAL, PRICE_FILTER antes de enviar orden
- [ ] placeOrder: `POST /api/v3/order` con `newClientOrderId` (idempotencia)
- [ ] getOpenOrders, getPositions, getBalance, getOrderStatus, cancelOrder

#### 4.2 BinanceFuturesDemo Adapter

- [ ] Implementar `lib/trading/binance-futures-demo.ts`
- [ ] REST base: `https://demo-fapi.binance.com`
- [ ] Misma interface BrokerAdapter
- [ ] Validacion runtime: rechazar si `BINANCE_ENV !== 'demo_futures'`
- [ ] Mismos controles: time sync, filtros exchangeInfo, idempotencia

#### 4.3 Market Data WebSocket

- [ ] Implementar `lib/trading/market-data-ws.ts`
- [ ] Conexion WebSocket a Binance Testnet: `wss://stream.testnet.binance.vision/ws/btcusdt@kline_1m`
- [ ] Buffer de 200 velas para indicadores
- [ ] Solo procesar cuando vela cierra (isClosed: true)
- [ ] Ping/pong + reconexion automatica controlada
- [ ] Fallback: si WS cae, polling REST cada 60s hasta reconexion

```typescript
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
    isClosed: data.k.x,
  };
  if (kline.isClosed) {
    candleBuffer.push(kline);
    recalculateIndicators();
  }
};
```

#### 4.4 User Stream + Eventos de Cuenta

- [ ] Crear listen key: `POST /api/v3/userDataStream`
- [ ] Conectar WebSocket: `wss://stream.testnet.binance.vision/ws/<listenKey>`
- [ ] Consumir eventos: executionReport (ordenes), outboundAccountPosition (balance)
- [ ] Keep-alive: `PUT /api/v3/userDataStream` cada 30 minutos
- [ ] Reconexion controlada si se pierde conexion

#### 4.5 Router de Entorno

- [ ] Implementar `lib/trading/broker-router.ts`:

```typescript
function getBrokerAdapter(): BrokerAdapter {
  const adapter = process.env.BROKER_ADAPTER;
  if (adapter === 'simulated') return new SimulatedBroker(config);
  if (adapter === 'spot_testnet') {
    if (process.env.BINANCE_ENV !== 'spot_testnet') throw new Error('BINANCE_ENV mismatch');
    if (process.env.TRADING_ENABLED !== 'true') throw new Error('Trading disabled');
    return new BinanceSpotTestnet(config);
  }
  if (adapter === 'demo_futures') {
    if (process.env.BINANCE_ENV !== 'demo_futures') throw new Error('BINANCE_ENV mismatch');
    if (process.env.TRADING_ENABLED !== 'true') throw new Error('Trading disabled');
    return new BinanceFuturesDemo(config);
  }
  throw new Error(`Unknown BROKER_ADAPTER: ${adapter}`);
}
```

- [ ] Loguear base URL efectiva en cada operacion

#### 4.6 Variables de Entorno Fase 3

```env
# Binance router
BINANCE_ENV=spot_testnet   # spot_testnet | demo_futures
TRADING_ENABLED=false      # Kill switch global, activar manualmente

# Spot Testnet
BINANCE_SPOT_BASE_URL=https://testnet.binance.vision
BINANCE_SPOT_WS_URL=wss://stream.testnet.binance.vision/ws

# Futures Demo
BINANCE_FUTURES_BASE_URL=https://demo-fapi.binance.com
BINANCE_FUTURES_WS_URL=wss://fstream.binancefuture.com

# Credenciales
BINANCE_API_KEY=
BINANCE_API_SECRET=
```

---

### Semana 10: Reconciliacion + Dead-Letter

#### 4.7 Reconciliacion Periodica

- [ ] Implementar `lib/trading/reconciliation.ts`
- [ ] Corre cada 60 segundos (Vercel Cron o setInterval en long-running process)
- [ ] Flujo:

```typescript
async function reconcile(): Promise<ReconciliationResult> {
  // 1. Consultar estado real del exchange
  const exchangeOrders = await broker.getOpenOrders();
  const exchangePositions = await broker.getPositions();
  const exchangeBalance = await broker.getBalance();

  // 2. Consultar estado en DB
  const dbOrders = await getActiveOrdersFromDB();

  // 3. Detectar divergencias
  const divergences = [];

  // Ordenes en exchange que no estan en DB (huerfanas)
  for (const order of exchangeOrders) {
    if (!dbOrders.find(o => o.client_order_id === order.clientOrderId)) {
      divergences.push({ type: 'orphan_exchange_order', order });
    }
  }

  // Ordenes en DB marcadas 'submitted' pero no en exchange (missing)
  for (const order of dbOrders) {
    if (!exchangeOrders.find(o => o.clientOrderId === order.client_order_id)) {
      divergences.push({ type: 'missing_exchange_order', order });
    }
  }

  // 4. Reparar y alertar
  for (const d of divergences) {
    await repairDivergence(d);
    await telegram.sendAlert(`Divergencia: ${d.type} - ${d.order.client_order_id}`);
  }

  // 5. Guardar resultado
  return await saveReconciliationRun({
    orders_synced: exchangeOrders.length,
    positions_synced: exchangePositions.length,
    divergences_found: divergences.length,
    divergence_details: divergences,
    balance_snapshot: exchangeBalance,
  });
}
```

#### 4.8 Dead-Letter Queue

- [ ] Si una orden falla 3 veces (retry_count >= 3):
  - Status → `dead_letter`
  - Telegram alert inmediata: "Orden {id} movida a dead-letter. Requiere intervencion manual."
  - La propuesta asociada pasa a status `failed`
- [ ] API route para resolver dead-letters manualmente:
  - `POST /api/orders/[id]/retry` — reintentar
  - `POST /api/orders/[id]/cancel` — cancelar definitivamente

#### 4.9 API Routes Reconciliacion

```
POST   /api/reconciliation/run     - Trigger reconciliacion manual
GET    /api/reconciliation/history - Historial de reconciliaciones
GET    /api/reconciliation/latest  - Ultima reconciliacion con divergencias

POST   /api/orders/[id]/retry      - Reintentar orden dead-letter
POST   /api/orders/[id]/cancel     - Cancelar orden dead-letter
```

---

### Semana 11: Observabilidad Avanzada + MCP Binance

#### 4.10 Replay Avanzado de Historicos

- [ ] Implementar `lib/trading/replay-engine.ts`
- [ ] Cargar klines historicas desde CSV/JSON
- [ ] Alimentar SimulatedBroker con datos replay a velocidad configurable (1x, 10x, 50x)
- [ ] `POST /api/simulator/replay` — Iniciar replay
- [ ] Pagina `/simulator` actualizada con resultados de backtesting

#### 4.11 MCP Binance (read-only)

- [ ] Integrar `forgequant/mcp-provider-binance` para market data
- [ ] Solo herramientas read-only habilitadas:
  - `get_server_time`
  - `get_ticker`
  - `get_order_book`
  - `get_open_orders`
- [ ] Bloquear herramientas de escritura (`place_order`, `cancel_order`) en esta fase

#### 4.12 Pagina /history

- [ ] Historial completo: proposals → orders → fills
- [ ] Filtros por fecha, status, correlation_id
- [ ] Exportacion CSV
- [ ] Timeline visual por correlation_id (proposal → approval → execution → reconciliation)

#### 4.13 Health Check Avanzado

- [ ] `GET /api/operations/health` retorna:

```json
{
  "status": "healthy | degraded | unhealthy",
  "components": {
    "database": "ok | error",
    "ai_sdk": "ok | error",
    "telegram": "ok | error",
    "binance_ws": "connected | disconnected",
    "binance_rest": "ok | error",
    "reconciliation": "ok | stale | error"
  },
  "metrics": {
    "uptime_hours": 168,
    "last_reconciliation": "2026-03-15T10:30:00Z",
    "active_breakers": 0,
    "daily_pnl_usdt": 12.50,
    "daily_llm_cost_usd": 1.20
  }
}
```

#### 4.14 Telegram Alertas Enriquecidas

- [ ] Reporte diario automatico via Telegram (cron 00:00 UTC):
  - PnL del dia
  - Costo LLM
  - Trades ejecutados (ganadores/perdedores)
  - Breakers activados
  - Divergencias de reconciliacion
  - Estado de salud del sistema

---

### Semana 12: Piloto 7 Dias + Hardening

#### 4.15 Criterio de Graduacion (Simulador → Exchange)

Antes de activar `TRADING_ENABLED=true` con `BROKER_ADAPTER=spot_testnet`:

- [ ] Minimo 7 dias operando estable en simulador
- [ ] Sin circuit breakers activados en nivel critico
- [ ] Sharpe ratio > 0 (no pierde consistentemente)
- [ ] Error rate < 1%
- [ ] Reconciliacion sin divergencias por 48h
- [ ] Review manual de seguridad completado

#### 4.16 Piloto en Exchange Demo

- [ ] Activar `TRADING_ENABLED=true` + `BROKER_ADAPTER=spot_testnet`
- [ ] Operar con volumenes minimos (0.0001 BTC por trade)
- [ ] Monitoreo continuo de:
  - Breakers activos
  - Reconciliacion sin divergencias
  - Slippage real vs simulado
  - Latencia de ejecucion
  - Costo LLM acumulado
- [ ] Si cualquier breaker critico se activa: volver a `BROKER_ADAPTER=simulated` inmediatamente

#### 4.17 Documentacion Operativa

- [ ] Playbooks de fallo:
  - WS se desconecta → reconexion + fallback polling
  - Reconciliacion encuentra divergencia → alertar + investigar
  - Circuit breaker trading activado → esperar cooldown, review
  - Dead-letter acumulados → review manual, ajustar logica
  - Gemini API down → pausar agentes, fallback a ultima decision
- [ ] Runbook de operacion diaria:
  - Verificar /operations al inicio del dia
  - Revisar divergencias de reconciliacion
  - Verificar costo LLM vs presupuesto
  - Aprobar/rechazar propuestas pendientes
  - Resolver breakers activos si corresponde

#### 4.18 Review Final de Seguridad

- [ ] Verificar que NUNCA se puede enviar orden a produccion real
- [ ] Verificar que API keys de Binance son de testnet/demo
- [ ] Verificar que RLS esta activo en todas las tablas (incluyendo nuevas)
- [ ] Verificar que DELETE esta bloqueado en tablas de logs (inmutabilidad)
- [ ] Verificar que `TRADING_ENABLED=false` por default en todos los entornos
- [ ] Verificar que kill switch funciona (desactivar trading inmediatamente)

#### 4.19 Testing Fase 3

**Unit Tests:**
- [ ] BinanceSpotTestnet: firma HMAC correcta, time sync, filtros
- [ ] BinanceFuturesDemo: idem
- [ ] Reconciliacion: deteccion de divergencias (huerfanas, missing)
- [ ] Dead-letter: orden falla 3x → status dead_letter
- [ ] Router: adapter correcto segun env vars, rechaza combinaciones invalidas

**Integration Tests:**
- [ ] Proposal → approval → ejecucion en BinanceSpotTestnet (con mock)
- [ ] Reconciliacion contra estado divergente
- [ ] Dead-letter → alerta Telegram → retry manual
- [ ] Circuit breaker + reconciliacion: breaker bloquea, reconcilia estado

**E2E Tests:**
- [ ] /history: ver timeline completa de un trade
- [ ] /operations: health check muestra todos los componentes
- [ ] /simulator: replay historico completo + resultados
- [ ] Exportar CSV desde /history

## 5. Estructura de Archivos (nuevos en Fase 3)

```
lib/
  trading/
    binance-spot-testnet.ts         # Adapter Binance Spot
    binance-futures-demo.ts         # Adapter Binance Futures
    broker-router.ts                # Router por entorno
    market-data-ws.ts               # WebSocket market data
    user-stream.ts                  # WebSocket user events
    reconciliation.ts               # Reconciliacion periodica
    replay-engine.ts                # Replay datos historicos
app/
  history/page.tsx                  # Historial con exportacion CSV
  api/
    reconciliation/
      run/route.ts
      history/route.ts
      latest/route.ts
    orders/
      [id]/
        retry/route.ts
        cancel/route.ts
    telegram/
      daily-report/route.ts        # Cron: reporte diario
```

## 6. Gate de Salida (Fase 3 = Proyecto MVP Completo)

- [ ] Binance Spot Testnet adapter funcional con ordenes reales en testnet
- [ ] Reconciliacion automatica cada 60s sin divergencias por 48h
- [ ] Dead-letter funcional con alertas y retry manual
- [ ] 7 dias de operacion estable (en simulador o en exchange demo)
- [ ] Sharpe ratio > 0 sostenido
- [ ] Error rate < 1% sostenido
- [ ] Circuit breakers operativos en los 3 niveles
- [ ] Health check reporta todos los componentes healthy
- [ ] Reporte diario via Telegram funcionando
- [ ] Exportacion CSV desde /history
- [ ] Documentacion operativa completa (playbooks + runbooks)
- [ ] Review de seguridad pasado

## 7. Definition of Done (MVP Completo)

El MVP se considera completo cuando se cumplen TODOS estos criterios:

### Fase 1 (Research)
1. Pipeline: URL → evaluacion → extraccion → guia maestra funcional
2. RAG: chat responde con contexto de papers
3. Dashboard: todas las paginas operativas

### Fase 2 (Trading Core)
4. TradeProposal workflow completo (11 estados)
5. HITL via Telegram funcional
6. Risk Manager + Circuit Breakers operativos
7. SimulatedBroker estable

### Fase 3 (Exchange)
8. Binance adapter conectado a testnet real
9. Reconciliacion automatica sin divergencias 48h
10. Idempotencia validada (duplicados prevenidos)
11. Trazabilidad completa por correlation_id
12. Metricas operativas visibles en /operations
13. 7 dias estables en exchange demo
14. Reporte diario Telegram funcionando
15. Documentacion operativa lista

## 8. Riesgos Residuales (post-MVP)

| Riesgo | Mitigacion | Responsable |
|---|---|---|
| Drift APIs (Gemini/AI SDK/Binance) | Reauditoria CODEX por cambio de version | Operador |
| Pricing LLM cambia | Metricas de costo con alertas de presupuesto | Circuit breaker LLM |
| Degradacion RAG si crece dataset | Recalibrar match_threshold con precision@k | P1 pendiente |
| Ruido de mercado invalida paper trading | Analisis periodico de Sharpe + ajuste de guia | Synthesis Agent |
| Binance Testnet inestable | Fallback a SimulatedBroker automatico | Broker router |

## 9. Regla de Mantenimiento CODEX

Cada cambio de version de:
- Next.js
- AI SDK
- Gemini models
- Binance endpoints

Debe gatillar reauditoria y actualizacion del CODEX.
