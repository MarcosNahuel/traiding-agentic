# Fase 2: Trading Core + Simulador

**Proyecto:** traiding-agentic
**Duracion:** Semanas 5-8 (4 semanas)
**Prerequisitos:** Fase 1 completa (gate de salida aprobado)
**Estado:** Plan final validado
**Fecha:** 2026-02-15

---

## 1. Objetivo

Construir el trading bot que opera BTC/USDT en paper trading, alimentado por la Guia Maestra de Fase 1. Incluye simulador local con replay, HITL hibrido via Telegram, Risk Manager determinista, y Circuit Breakers avanzados. **NO se conecta a Binance real** — todo opera contra SimulatedBroker.

## 2. Decisiones Tecnicas Cerradas

| Decision | Valor | Origen |
|---|---|---|
| HITL level | Hibrido: auto < $100, manual >= $100 | Brainstorming |
| HITL SLA | 5 minutos para aprobar | Plan tecnico |
| Notificaciones | Telegram Bot (t.me/Traiding77bot) | Decision usuario |
| Broker inicial | SimulatedBroker (NO exchange real) | CODEX 13 |
| Event sourcing | Logs inmutables + correlation_id (no hash chain) | Brainstorming YAGNI |
| Graduacion | 7 dias estables en simulador antes de exchange | CODEX 13 |
| Circuit breakers | 3 niveles: trading + infra + LLM | Brainstorming |
| Capital simulado | 10,000 USDT | Plan tecnico |
| Par de trading | Solo BTCUSDT | Plan tecnico |
| Leverage | 1x (sin leverage) para MVP | Plan tecnico |
| Intervalo advisor | Cada 5 minutos | Plan tecnico |

## 3. Modelo de Datos (nuevas tablas)

### Migration 003_trading_schema.sql

```sql
-- Trade Proposals (toda decision del LLM pasa por aca)
CREATE TABLE trade_proposals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  correlation_id UUID NOT NULL DEFAULT gen_random_uuid(),
  symbol TEXT NOT NULL DEFAULT 'BTCUSDT',
  side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
  order_type TEXT NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT')),
  quantity NUMERIC(18,8) NOT NULL,
  price NUMERIC(18,2),
  notional_usdt NUMERIC(18,2) NOT NULL,
  strategy_name TEXT NOT NULL,
  reasoning TEXT,
  status TEXT NOT NULL CHECK (status IN (
    'draft', 'validated', 'risk_rejected',
    'auto_approved', 'pending_approval',
    'approved', 'rejected', 'expired',
    'executed', 'failed', 'cancelled'
  )) DEFAULT 'draft',
  approved_by TEXT,
  approval_reason TEXT,
  rejection_reason TEXT,
  risk_check_passed BOOLEAN,
  risk_check_details JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now(),
  validated_at TIMESTAMPTZ,
  approved_at TIMESTAMPTZ,
  executed_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ,
  indicators_snapshot JSONB DEFAULT '{}',
  guide_version INTEGER
);

CREATE INDEX idx_proposals_status ON trade_proposals(status);
CREATE INDEX idx_proposals_correlation ON trade_proposals(correlation_id);
CREATE INDEX idx_proposals_created ON trade_proposals(created_at DESC);
ALTER TABLE trade_proposals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_full_access" ON trade_proposals FOR ALL USING (true);

-- Execution Orders
CREATE TABLE execution_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  proposal_id UUID NOT NULL REFERENCES trade_proposals(id),
  correlation_id UUID NOT NULL,
  client_order_id UUID NOT NULL UNIQUE,
  exchange_order_id TEXT,
  broker_adapter TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  order_type TEXT NOT NULL,
  quantity NUMERIC(18,8) NOT NULL,
  requested_price NUMERIC(18,2),
  fill_price NUMERIC(18,2),
  fill_quantity NUMERIC(18,8),
  slippage_bps NUMERIC(10,2),
  commission NUMERIC(18,8),
  status TEXT NOT NULL CHECK (status IN (
    'pending', 'submitted', 'partially_filled',
    'filled', 'cancelled', 'rejected', 'expired',
    'failed', 'dead_letter'
  )) DEFAULT 'pending',
  error_message TEXT,
  retry_count INTEGER DEFAULT 0,
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

-- Risk Breaker Events
CREATE TABLE risk_breaker_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  breaker_name TEXT NOT NULL,
  breaker_category TEXT NOT NULL CHECK (breaker_category IN ('trading', 'infrastructure', 'llm')),
  trigger_value NUMERIC(18,4) NOT NULL,
  threshold_value NUMERIC(18,4) NOT NULL,
  action_taken TEXT NOT NULL,
  notification_sent BOOLEAN DEFAULT false,
  resolved_at TIMESTAMPTZ,
  resolved_by TEXT,
  resolution_notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_breakers_name ON risk_breaker_events(breaker_name);
CREATE INDEX idx_breakers_created ON risk_breaker_events(created_at DESC);
CREATE INDEX idx_breakers_active ON risk_breaker_events(resolved_at) WHERE resolved_at IS NULL;
ALTER TABLE risk_breaker_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_full_access" ON risk_breaker_events FOR ALL USING (true);

-- Agregar campos a agent_logs para trazabilidad trading
ALTER TABLE agent_logs ADD COLUMN IF NOT EXISTS correlation_id UUID;
ALTER TABLE agent_logs ADD COLUMN IF NOT EXISTS actor TEXT DEFAULT 'agent'
  CHECK (actor IN ('agent', 'human', 'system', 'breaker'));
CREATE INDEX IF NOT EXISTS idx_logs_correlation ON agent_logs(correlation_id);
```

## 4. Entregables por Semana

### Semana 5: Indicators + Risk Manager + Proposal Workflow

#### 4.1 Indicators Engine

- [ ] Implementar `lib/utils/indicators.ts`
- [ ] Indicadores calculados sobre buffer de 200 velas:

```typescript
interface Indicators {
  sma_10: number;
  sma_50: number;
  rsi_14: number;
  bb_upper: number;
  bb_lower: number;
  bb_middle: number;
  volume_avg_20: number;
  volume_ratio: number;
  atr_14: number;
}
```

- [ ] Unit tests para cada indicador con datos conocidos

#### 4.2 Risk Manager (determinista)

- [ ] Implementar `lib/utils/risk-manager.ts`
- [ ] Limites fijos en codigo (NO controlados por LLM):

```typescript
interface RiskLimits {
  maxDailyLossPct: 2;
  maxPositionSizeBTC: 0.001;    // ~$100 por trade
  maxOpenPositions: 1;
  stopLossPct: 1.5;
  takeProfitPct: 3;
  maxLeverage: 1;               // Sin leverage
  cooldownAfterLossMinutes: 30;
}
```

- [ ] Validar propuesta contra limites
- [ ] Retornar {passed: boolean, details: {...}} con razon de rechazo si falla

#### 4.3 Trade Proposal Workflow (maquina de estados)

- [ ] Implementar `lib/trading/proposal-workflow.ts`
- [ ] Maquina de estados completa:

```
draft → validated → auto_approved → executed | failed
                  → pending_approval → approved → executed | failed
                                     → rejected
                                     → expired
                  → risk_rejected
                  → cancelled
```

- [ ] Transiciones validadas (no se puede saltar estados)
- [ ] Timer de expiracion: expires_at = created_at + HITL_SLA_SECONDS
- [ ] Logging de cada transicion con correlation_id

#### 4.4 HITL via Telegram

- [ ] Extender `lib/utils/telegram.ts`:
  - `sendProposalNotification(proposal)` — Envia propuesta con botones inline (Aprobar/Rechazar)
  - `sendBreakerAlert(event)` — Alerta de circuit breaker
  - Webhook handler para recibir respuestas de Telegram
- [ ] Flujo completo:
  1. Propuesta con notional >= $100 → status: pending_approval
  2. Mensaje Telegram: "Nueva propuesta: BUY 0.001 BTC @ $98,500 ($98.50). Razon: [reasoning]. [Aprobar] [Rechazar]"
  3. Operador toca boton → webhook → update status
  4. Si no responde en 5 min → status: expired

#### 4.5 Variables de Entorno Fase 2

```env
# Trading
TRADING_ENABLED=false
BROKER_ADAPTER=simulated

# HITL
AUTO_APPROVE_THRESHOLD_USDT=100
HITL_SLA_SECONDS=300

# Circuit Breakers
MAX_DAILY_LLM_COST_USD=5
MAX_CONSECUTIVE_LOSSES=3
```

---

### Semana 6: SimulatedBroker + Strategy Advisor

#### 4.6 BrokerAdapter Interface

- [ ] Implementar `lib/trading/broker-adapter.ts`:

```typescript
interface BrokerAdapter {
  placeOrder(proposal: ValidatedProposal): Promise<OrderResult>;
  cancelOrder(orderId: string): Promise<CancelResult>;
  getOpenOrders(): Promise<Order[]>;
  getPositions(): Promise<Position[]>;
  getBalance(): Promise<Balance>;
  getOrderStatus(orderId: string): Promise<OrderStatus>;
}
```

#### 4.7 SimulatedBroker

- [ ] Implementar `lib/trading/simulated-broker.ts`:

```typescript
interface SimulatorConfig {
  initialBalanceUsdt: number;     // default 10000
  slippageBps: number;            // default 5 (0.05%)
  simulatedLatencyMs: number;     // default 100
  replayMode: boolean;
  replayDataPath?: string;        // CSV/JSON de klines historicas
  replaySpeedMultiplier?: number; // 1x = real, 10x = rapido
}
```

- [ ] Balance virtual + posiciones en DB
- [ ] Slippage configurable aplicado al fill
- [ ] Latencia simulada
- [ ] Soporte para replay de datos historicos
- [ ] Idempotencia: client_order_id UNIQUE, duplicados ignorados

#### 4.8 Strategy Advisor

- [ ] Implementar loop principal (cada 5 minutos):
  1. Recopilar indicadores actuales del buffer de velas
  2. Cargar system prompt de la guia maestra actual
  3. Enviar a Gemini con generateObject + schema de propuesta
  4. Crear TradeProposal (draft)
  5. Pasar por Risk Manager
  6. Evaluar threshold HITL
  7. Ejecutar o notificar segun corresponda

- [ ] El advisor NO genera ordenes directas, solo proposals
- [ ] Snapshot de indicadores guardado en cada proposal

#### 4.9 API Routes Semana 5-6

```
POST   /api/proposals              - Crear propuesta (uso interno)
GET    /api/proposals              - Listar (?status=pending_approval)
GET    /api/proposals/[id]         - Detalle con ordenes
POST   /api/proposals/[id]/approve - Aprobar (humano o auto)
POST   /api/proposals/[id]/reject  - Rechazar (body: {reason})

GET    /api/orders                 - Listar ordenes
GET    /api/orders/[id]            - Detalle con fill info

POST   /api/simulator/config       - Configurar simulador
GET    /api/simulator/status        - Estado del simulador
```

---

### Semana 7: Circuit Breakers + Observabilidad

#### 4.10 Circuit Breakers Avanzados

- [ ] Implementar `lib/utils/circuit-breakers.ts`
- [ ] 3 categorias, 7 breakers:

```typescript
interface CircuitBreakers {
  // Trading
  maxConsecutiveLosses: 3;
  maxDailyLossPct: 2;

  // Infrastructure
  maxSlippageBps: 20;
  latencyGuardMs: 5000;
  maxOrderRejectionsPerHour: 5;

  // LLM
  maxLlmErrorsPerHour: 10;
  maxDailyLlmCostUsd: 5;
}
```

- [ ] Acciones por breaker:

| Breaker | Accion | Notificacion |
|---|---|---|
| maxConsecutiveLosses | Bloquear ordenes | Telegram alert |
| maxDailyLossPct | Bloquear + cerrar posiciones | Telegram alert |
| maxSlippageBps | Pausar 15 min | Telegram alert |
| latencyGuardMs | Pausar trading | Telegram alert |
| maxOrderRejectionsPerHour | Bloquear ordenes | Telegram alert |
| maxLlmErrorsPerHour | Pausar agentes LLM | Telegram alert |
| maxDailyLlmCostUsd | Pausar agentes LLM | Telegram alert |

- [ ] Cada activacion registrada en risk_breaker_events
- [ ] Resolucion: manual via API o automatica por timeout

#### 4.11 Observabilidad

- [ ] Metricas operativas:

| Metrica | Calculo |
|---|---|
| proposal_to_approval_ms | approved_at - created_at |
| approval_to_execution_ms | executed_at - approved_at |
| fill_rate | executed / total proposals |
| rejection_rate | (rejected + risk_rejected) / total |
| slippage_bps_realized | (fill_price - proposal_price) / proposal_price * 10000 |
| breaker_trigger_count | COUNT(risk_breaker_events) per day |
| llm_tokens_cost_daily | SUM(estimated_cost_usd) per agent per day |
| sharpe_ratio_rolling | (avg_return - risk_free) / std_return (30 dias) |
| win_rate | winning_trades / total_closed_trades |

#### 4.12 API Routes Semana 7

```
GET    /api/risk/breakers          - Estado actual de todos los breakers
GET    /api/risk/breakers/history  - Historial de activaciones
POST   /api/risk/breakers/[name]/resolve - Resolver manualmente

GET    /api/operations/metrics     - KPIs operativos
GET    /api/operations/pnl         - PnL diario/acumulado
GET    /api/operations/health      - Health check del sistema
```

---

### Semana 8: Frontend Trading + Testing

#### 4.13 Frontend Pages

**Pagina /approvals:**
- [ ] Cola HITL: propuestas pendientes
- [ ] Timer visual de SLA (countdown 5 min)
- [ ] Detalles: indicadores, razon del LLM, notional
- [ ] Botones aprobar/rechazar
- [ ] Auto-refresh (polling cada 5s o SWR revalidation)

**Pagina /trading:**
- [ ] Dashboard live:
  - Precio BTC (del simulador)
  - Posicion abierta actual con P&L
  - PnL del dia y acumulado
  - Ultimo trade
  - Stop-loss y take-profit actuales
  - Log de decisiones del agente

**Pagina /operations:**
- [ ] Estado de circuit breakers (indicadores verde/amarillo/rojo)
- [ ] Metricas operativas (tabla)
- [ ] Log de eventos con filtro por correlation_id
- [ ] Costo LLM del dia
- [ ] Proxima reconciliacion (placeholder para Fase 3)

**Pagina /simulator:**
- [ ] Configuracion: balance, slippage, latencia
- [ ] Estado actual del simulador
- [ ] Replay de datos historicos (iniciar/detener)

#### 4.14 Testing

**Unit Tests:**
- [ ] Indicadores: SMA, RSI, Bollinger, ATR con datos conocidos
- [ ] Risk Manager: validar que rechaza propuestas fuera de limites
- [ ] Transicion de estados HITL: todos los caminos de la maquina
- [ ] Circuit breakers: activacion/desactivacion por cada tipo
- [ ] SimulatedBroker: fill con slippage, balance tracking, posiciones
- [ ] Idempotencia: doble submit con mismo client_order_id

**Integration Tests:**
- [ ] Propuesta → auto-approve (< $100) → ejecucion simulada → log
- [ ] Propuesta → pending_approval → approve → ejecucion
- [ ] Propuesta → risk_rejected (por limite excedido o breaker activo)
- [ ] Circuit breaker se activa por perdidas consecutivas → bloquea nuevas ordenes

**E2E Tests:**
- [ ] /approvals: ver propuesta pendiente, aprobar, verificar ejecucion
- [ ] /trading: verificar que muestra datos del simulador
- [ ] /operations: verificar metricas y estado de breakers

## 5. Estructura de Archivos (nuevos en Fase 2)

```
lib/
  trading/
    broker-adapter.ts               # Interface BrokerAdapter
    simulated-broker.ts             # Broker simulado local
    proposal-workflow.ts            # Maquina de estados TradeProposal
    strategy-advisor.ts             # Loop cada 5 min (Gemini + Guia)
  utils/
    indicators.ts                   # Technical indicators
    risk-manager.ts                 # Risk limits deterministas
    circuit-breakers.ts             # Circuit breakers avanzados
    telegram.ts                     # (extendido con HITL buttons)
components/
  approvals/                        # HITL approval queue
  operations/                       # Operations center
  simulator/                        # Simulator config
  trading/                          # Live trading dashboard
app/
  approvals/page.tsx
  trading/page.tsx
  operations/page.tsx
  simulator/page.tsx
  api/
    proposals/...
    orders/...
    risk/...
    operations/...
    simulator/...
    telegram/
      webhook/route.ts              # Webhook para botones Telegram
```

## 6. Gate de Salida (Fase 2 → Fase 3)

- [ ] SimulatedBroker funcional con slippage y balance tracking
- [ ] TradeProposal workflow completo (11 estados)
- [ ] HITL via Telegram: notificaciones y botones funcionando
- [ ] Risk Manager rechaza propuestas fuera de limites
- [ ] Circuit breakers se activan y bloquean operaciones correctamente
- [ ] Idempotencia: client_order_id UNIQUE previene duplicados
- [ ] Metricas operativas visibles en /operations
- [ ] Strategy Advisor genera proposals basado en indicadores + guia
- [ ] Al menos 48h de operacion estable en simulador sin errores criticos
- [ ] Tests unitarios, integracion y E2E pasando

## 7. Definition of Done

Fase 2 esta completa cuando:

1. No hay ejecucion de orden sin pasar por TradeProposal workflow
2. HITL funcional: ordenes >= $100 requieren aprobacion via Telegram
3. Ordenes < $100 se auto-aprueban y ejecutan automaticamente
4. SimulatedBroker opera con balance virtual y slippage realista
5. Circuit breakers protegen contra perdidas, latencia y costos LLM
6. Todas las acciones tienen correlation_id para trazabilidad
7. Dashboard muestra estado completo del trading simulado

## 8. Lo que NO se hace en Fase 2

- NO se conecta a Binance real (ni Testnet ni Futures Demo)
- NO se implementa reconciliacion con exchange (no hay exchange)
- NO se implementa WebSocket a Binance (se usa data simulada/replay)
- NO se implementa replay avanzado de historicos (basico si)
- NO se exporta a CSV (Fase 3)
- NO se implementa push notifications de browser (Telegram es suficiente)
